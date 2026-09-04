// Sanity test for the bottom-left popup menu "Check for updates" button.
//
// Loads renderer/index.html into JSDOM, stubs window.kt with a controllable
// mock IPC bridge, runs renderer/app.js, then simulates:
//   1. clicking the menu trigger,
//   2. clicking "Check for updates",
//   3. verifying IPC was invoked and the status text updated.

const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const HTML_PATH = path.join(__dirname, 'renderer', 'index.html');
const APP_JS_PATH = path.join(__dirname, 'renderer', 'app.js');

const html = fs.readFileSync(HTML_PATH, 'utf8');
const appJs = fs.readFileSync(APP_JS_PATH, 'utf8');

(async () => {
  // Strip the <link> tags because the stylesheets do not exist in this
  // sandbox and we don't want network errors.
  const safeHtml = html.replace(/<link[^>]+>/g, '');

  // Inject our mock bridge and a setTimeout-based rAF BEFORE the renderer
  // script runs. JSDOM's rAF depends on a real rendering loop which we
  // don't have here.
  const preamble = `
    (function () {
      var ipcInvocations = [];
      var updateAvailableListeners = [];
      var updateNotAvailableListeners = [];
      var updateDownloadedListeners = [];
      var updateErrorListeners = [];
      window.kt = {
        getCredentials: async () => ({}),
        getCompendiumPath: async () => '',
        getHermesHome: async () => '',
        getLogs: async () => [],
        getNousModels: async () => [],
        authSubscriptionStatus: async () => ({ status: 'active' }),
        getAppVersion: async () => '1.1.17',
        checkHermes: async () => ({ installed: false }),
        getDashboardStatus: async () => ({ running: false }),
        checkForUpdates: async () => {
          ipcInvocations.push('checkForUpdates');
          setTimeout(function () {
            updateAvailableListeners.forEach(function (cb) { cb({ version: '1.1.18' }); });
          }, 5);
          return { ok: true };
        },
        onLogLine: function () { return function () {}; },
        onDashboardReady: function () { return function () {}; },
        onDashboardStopped: function () { return function () {}; },
        onUpdateAvailable: function (cb) { updateAvailableListeners.push(cb); return function () {}; },
        onUpdateNotAvailable: function (cb) { updateNotAvailableListeners.push(cb); return function () {}; },
        onUpdateDownloaded: function (cb) { updateDownloadedListeners.push(cb); return function () {}; },
        onUpdateError: function (cb) { updateErrorListeners.push(cb); return function () {}; },
        onSubscriptionLocked: function () { return function () {}; },
        openExternal: async () => {},
        quitAndInstallUpdate: async () => {},
        getCronPrompt: async () => '',
        announceVoice: async () => {},
        pickNousCredentialFile: async () => '',
        pickBlofinCredentialFile: async () => '',
        authLogin: async () => ({ ok: true }),
        authForgotPassword: async () => ({ ok: true }),
        authLogout: async () => {},
        authCreateCheckoutSession: async () => ({ ok: true, url: 'https://example.com' }),
        vpnStatus: async () => ({}),
        vpnDetect: async () => ({}),
        vpnConnect: async () => ({}),
        vpnDisconnect: async () => ({}),
        vpnAllowed: async () => ([]),
      };
      window.__ipcInvocations = ipcInvocations;
      window.requestAnimationFrame = function (cb) {
        return window.setTimeout(function () { cb(Date.now()); }, 0);
      };
      window.cancelAnimationFrame = function (id) {
        return window.clearTimeout(id);
      };
    })();
  `;

  // Inject the renderer script inline so it executes in the same global
  // scope as our window.kt mock.
  const htmlWithScript = safeHtml.replace(
    '</body>',
    '<script>\n' + preamble + '\n</script>\n<script>\n' + appJs + '\n</script></body>'
  );

  const dom = new JSDOM(htmlWithScript, {
    url: 'file://' + HTML_PATH.replace(/\\/g, '/'),
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    resources: undefined,
  });
  const { window } = dom;
  const { document } = window;

  // Catch any errors thrown by the renderer script so we don't fail silently.
  window.addEventListener('error', (e) => {
    console.error('[renderer error]', e.error && e.error.stack || e.message);
  });

  await new Promise((r) => setTimeout(r, 200));

  const trigger = document.getElementById('btn-popup-trigger');
  if (!trigger) throw new Error('btn-popup-trigger missing from DOM');

  console.log('Step 1: clicking menu trigger');
  const triggerEvent = new window.MouseEvent('click', { bubbles: true, cancelable: true });
  trigger.dispatchEvent(triggerEvent);

  await new Promise((r) => setTimeout(r, 100));

  const popupMenu = document.getElementById('popup-menu');
  if (!popupMenu) throw new Error('popup-menu missing from DOM');
  console.log('  popupMenu.hidden AFTER click + rAF:', popupMenu.classList.contains('hidden'));
  if (popupMenu.classList.contains('hidden')) {
    throw new Error('popup-menu should be visible after clicking trigger');
  }
  const checkBtn = popupMenu.querySelector('#btn-check-for-updates');
  if (!checkBtn) {
    throw new Error('Check for updates button not found after popup opened');
  }
  console.log('  popup visible, button present');

  // Idempotency: open/close several times to make sure the button stays
  // wired up across rebuilds.
  console.log('Step 1b: open/close x3 to confirm idempotency');
  for (let i = 0; i < 3; i++) {
    trigger.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
    await new Promise((r) => setTimeout(r, 50));
    trigger.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
    await new Promise((r) => setTimeout(r, 50));
  }
  if (popupMenu.classList.contains('hidden')) {
    throw new Error('popup-menu should be open after final trigger click');
  }
  const checkBtnAfter = popupMenu.querySelector('#btn-check-for-updates');
  if (!checkBtnAfter) throw new Error('Check for updates button missing after reopen cycles');

  console.log('Step 2: clicking Check for updates');
  const btnEvent = new window.MouseEvent('click', { bubbles: true, cancelable: true });
  checkBtnAfter.dispatchEvent(btnEvent);

  await new Promise((r) => setTimeout(r, 100));

  console.log('Step 3: verifying side effects');
  const invs = window.__ipcInvocations || [];
  console.log('  IPC invocations:', invs);
  if (invs.indexOf('checkForUpdates') < 0) {
    throw new Error('checkForUpdates IPC was NOT invoked');
  }
  const status = popupMenu.querySelector('#popup-update-status');
  const version = popupMenu.querySelector('#popup-app-version');
  console.log('  popup status text:', JSON.stringify(status && status.textContent));
  console.log('  popup version text:', JSON.stringify(version && version.textContent));

  if (!status) throw new Error('popup-update-status missing');
  if (!(status.textContent.indexOf('Update available') >= 0)) {
    throw new Error('Expected status to mention "Update available", got "' + status.textContent + '"');
  }
  if (!version) throw new Error('popup-app-version missing');
  if (!(version.textContent.indexOf('1.1.17') >= 0)) {
    throw new Error('Expected version to be "1.1.17", got "' + version.textContent + '"');
  }

  console.log('\nALL CHECKS PASSED');
  process.exit(0);
})().catch((e) => {
  console.error('\nTEST FAILED:', e.message);
  console.error(e.stack);
  process.exit(1);
});