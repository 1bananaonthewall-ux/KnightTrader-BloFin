/* ── KnightTrader App Logic v2 ─────────────────────────────── */

let currentTab = 'howto';
let autoScroll = true;
let newLogs = 0;
let hermesInstalled = false;
let dashboardRunning = false;
let dashboardStartInFlight = false;
let authReady = false;

// ── DOM shortcuts ─────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const el = {
  minimize: $('btn-minimize'), maximize: $('btn-maximize'), close: $('btn-close'),

  // VPN helper
  vpnCountry: $('vpn-country'),
  btnVpnGuide: $('btn-vpn-guide'),
  vpnStatus: $('vpn-status'),
  navItems: document.querySelectorAll('.nav-item'),
  tabPanels: document.querySelectorAll('.tab-panel'),
  statusPill: $('status-pill'), statusOrb: $('status-orb'), statusLabel: $('status-label'),
  logBadge: $('log-badge'), hermesNavBadge: $('hermes-nav-badge'),

  // Setup
  formSetup: $('form-setup'),
  nousApiKey: $('nous-api-key'), nousModel: $('nous-model'),
  btnLoadNousFile: $('btn-load-nous-file'), nousFilePath: $('nous-file-path'),
  btnTestNous: $('btn-test-nous'), nousTestStatus: $('nous-test-status'),
  blofinApiKey: $('blofin-api-key'), blofinSecretKey: $('blofin-secret-key'), blofinPassphrase: $('blofin-passphrase'),
  blofinDemoMode: $('blofin-demo-mode'),
  btnLoadBlofinFile: $('btn-load-blofin-file'), blofinFilePath: $('blofin-file-path'),
  btnTestBlofin: $('btn-test-blofin'), blofinTestStatus: $('blofin-test-status'),
  saveStatus: $('save-status'), btnSave: $('btn-save'),

  // Hermes tab
  hermesInstallStatus: $('hermes-install-status'), btnInstallHermes: $('btn-install-hermes'),
  hermesVersionTag: $('hermes-version-tag'), hermesHomeDisplay: $('hermes-home-display'),
  btnWriteCompendium: $('btn-write-compendium'), compendiumStatus: $('compendium-status'),
  compendiumPathDisplay: $('compendium-path-display'),
  btnStartDashboard: $('btn-start-dashboard'), btnStopDashboard: $('btn-stop-dashboard'),
  dashboardStatus: $('dashboard-status'),
  btnConfigureCron: $('btn-configure-cron'), cronStatus: $('cron-status'),
  manualPromptWrap: $('manual-prompt-wrap'), cronPromptText: $('cron-prompt-text'), btnCopyPrompt: $('btn-copy-prompt'),
  dashboardEmbedWrap: $('dashboard-embed-wrap'), dashUrl: $('dash-url'),
  hermesWebview: $('hermes-webview'),
  btnReloadDash: $('btn-reload-dash'), btnOpenDashExternal: $('btn-open-dash-external'),

  // Logs
  logContainer: $('log-container'), logList: $('log-list'), logEmpty: $('log-empty'),
  btnAutoscroll: $('btn-autoscroll'), btnClearLogs: $('btn-clear-logs'),

  // Settings
  aboutHermesVer: $('about-hermes-ver'),
  aboutAppVersion: $('about-app-version'),

  // Trading
  tradingWebview: $('trading-webview'),
  tradingWebviewWrap: $('trading-webview-wrap'),
  btnReloadTrading: $('btn-reload-trading'),

  // Sidebar / updates
  sidebarVersion: $('sidebar-version'),

  // Update popup menu
  popupLauncher: $('popup-launcher'),
  popupMenu: $('popup-menu'),
  btnPopupTrigger: $('btn-popup-trigger'),
  btnCheckForUpdates: $('btn-check-for-updates'),
  popupUpdateStatus: $('popup-update-status'),
  popupAppVersion: $('popup-app-version'),

  // Update banner
  updateBanner: $('update-banner'),
  updateBannerTitle: $('update-banner-title'),
  updateBannerText: $('update-banner-text'),
  btnRestartUpdate: $('btn-restart-update'),
  btnDismissUpdate: $('btn-dismiss-update'),

  // Auth
  loginOverlay: $('login-overlay'),
  formLogin: $('form-login'),
  formForgot: $('form-forgot'),
  loginEmail: $('login-email'),
  loginPassword: $('login-password'),
  btnLogin: $('btn-login'),
  loginError: $('login-error'),
  btnForgot: $('btn-forgot'),
  forgotEmail: $('forgot-email'),
  forgotError: $('forgot-error'),
  forgotSuccess: $('forgot-success'),
  btnForgotSend: $('btn-forgot-send'),
  btnForgotBack: $('btn-forgot-back'),
};

function setLoginError(message) {
  if (!el.loginError) return;
  el.loginError.textContent = message || '';
}
function setForgotError(message) {
  if (!el.forgotError) return;
  el.forgotError.textContent = message || '';
}
function setForgotSuccess(message) {
  if (!el.forgotSuccess) return;
  el.forgotSuccess.textContent = message || '';
}
function showLoginForm() {
  if (el.loginOverlay) el.loginOverlay.classList.remove('hidden');
  if (el.formLogin) el.formLogin.classList.remove('hidden');
  if (el.formForgot) el.formForgot.classList.add('hidden');
  setLoginError('');
  setForgotError('');
  setForgotSuccess('');
}
function showForgotForm() {
  if (el.loginOverlay) el.loginOverlay.classList.remove('hidden');
  if (el.formLogin) el.formLogin.classList.add('hidden');
  if (el.formForgot) el.formForgot.classList.remove('hidden');
  setLoginError('');
  setForgotError('');
  setForgotSuccess('');
}
function hideLoginOverlay() {
  if (el.loginOverlay) el.loginOverlay.classList.add('hidden');
}
async function requireAuth() {
  try {
    const status = await window.kt.authSubscriptionStatus();
    if (status?.status === 'active') {
      authReady = true;
      hideLoginOverlay();
      return true;
    }
  } catch {}
  authReady = false;
  showLoginForm();
  return false;
}
async function handleLoginSubmit(e) {
  e.preventDefault();
  setLoginError('');
  const email = el.loginEmail?.value || '';
  const password = el.loginPassword?.value || '';
  if (!email || !password) {
    setLoginError('Enter both email and password.');
    return;
  }
  if (el.btnLogin) { el.btnLogin.disabled = true; el.btnLogin.textContent = 'Signing in...'; }
  try {
    const result = await window.kt.authLogin({ email, password });
    if (!result?.ok || !['active', 'missing_customer', 'inactive', 'stripe_unavailable'].includes(result.status)) {
      setLoginError(result?.msg || 'Membership login failed.');
      return;
    }
    authReady = true;
    hideLoginOverlay();
  } catch (err) {
    setLoginError(err?.message || 'Login failed.');
  } finally {
    if (el.btnLogin) { el.btnLogin.disabled = false; el.btnLogin.textContent = 'Sign in'; }
  }
}
async function handleForgotSubmit(e) {
  e.preventDefault();
  setForgotError('');
  setForgotSuccess('');
  const email = el.forgotEmail?.value || '';
  if (!email) {
    setForgotError('Enter the email for your account.');
    return;
  }
  if (el.btnForgotSend) { el.btnForgotSend.disabled = true; el.btnForgotSend.textContent = 'Sending...'; }
  try {
    const result = await window.kt.authForgotPassword(email);
    if (!result?.ok) {
      setForgotError(result?.msg || 'Password reset failed.');
      return;
    }
    setForgotSuccess(result.msg || 'If an account exists, a reset link has been sent.');
    setForgotError('');
  } catch (err) {
    setForgotError(err?.message || 'Password reset failed.');
  } finally {
    if (el.btnForgotSend) { el.btnForgotSend.disabled = false; el.btnForgotSend.textContent = 'Send reset link'; }
  }
}
function applySubscriptionLock(status) {
  authReady = false;
  const lockOverlay = $('subscription-lock-overlay');
  const lockMessage = $('lock-message');
  if (lockOverlay) {
    lockOverlay.classList.remove('hidden');
  }
  if (lockMessage) {
    lockMessage.textContent = status?.msg || 'Your membership is not active. Trading and Hermes cron are paused.';
  }
  if (el.statusLabel) el.statusLabel.textContent = 'Membership required';
  if (el.statusPill) el.statusPill.classList.remove('running');
  appendLogLine({ ts: new Date().toISOString(), level: 'warn', message: `🔒 ${status?.msg || 'Active membership required.'}` });
  pauseHermesForSubscription();
}
function hideSubscriptionLock() {
  const lockOverlay = $('subscription-lock-overlay');
  if (lockOverlay) lockOverlay.classList.add('hidden');
}
function openStripeCheckout() {
  const email = (el.loginEmail?.value || '').trim() || (sessionStorage.getItem('kt-last-email') || '').trim();
  if (!email) {
    setLoginError('Enter your membership email before opening checkout.');
    return;
  }
  window.kt.authCreateCheckoutSession(email).then((result) => {
    if (result?.ok && result.url) {
      window.kt.openExternal(result.url);
    } else {
      setLoginError(result?.msg || 'Could not open checkout.');
    }
  });
}
async function enforceSubscriptionOnLaunch() {
  try {
    const status = await window.kt.authSubscriptionStatus();
    if (status?.status !== 'active') {
      applySubscriptionLock(status || { msg: 'Active membership required.' });
      return false;
    }
    hideSubscriptionLock();
    return true;
  } catch {
    return true;
  }
}
function pauseHermesForSubscription() {
  if (el.btnStopDashboard && !el.btnStopDashboard.classList.contains('hidden')) {
    el.btnStopDashboard.click();
  }
}

// ── Init ──────────────────────────────────────────────────────
async function populateNousModels() {
  if (!el.nousModel) return;
  const previous = el.nousModel.value;
  try {
    const catalog = await window.kt.getNousModels();
    if (!catalog?.free?.length) return;
    el.nousModel.innerHTML = '';
    const freeGroup = document.createElement('optgroup');
    freeGroup.label = 'Free tier';
    for (const model of catalog.free) {
      const opt = document.createElement('option');
      opt.value = model.id;
      opt.textContent = model.label || model.id;
      freeGroup.appendChild(opt);
    }
    el.nousModel.appendChild(freeGroup);
    if (catalog.paid?.length) {
      const paidGroup = document.createElement('optgroup');
      paidGroup.label = 'Paid / subscription';
      for (const model of catalog.paid) {
        const opt = document.createElement('option');
        opt.value = model.id;
        opt.textContent = model.label || model.id;
        paidGroup.appendChild(opt);
      }
      el.nousModel.appendChild(paidGroup);
    }
    setNousModelValue(previous || catalog.defaultModel || 'tencent/hy3:free');
  } catch (_) {}
}

async function init() {
  if (el.loginOverlay && !el.loginOverlay.classList.contains('hidden')) {
    if (!(await requireAuth())) return;
  }
  await populateNousModels();
  // Detect whether the preload bridge actually reached the renderer.
  if (!window.kt) {
    throw new Error('window.kt is not available; preload bridge may have failed');
  }

  try {
    const appVersion = await window.kt.getAppVersion();
    const normalized = appVersion ? String(appVersion).replace(/^v/, '') : '';
    const label = normalized ? `v${normalized}` : '1.0.0';
    if (el.popupAppVersion) el.popupAppVersion.textContent = normalized;
    if (el.sidebarVersion) el.sidebarVersion.textContent = label;
    if (el.aboutAppVersion) el.aboutAppVersion.textContent = `KnightTrader ${label}`;
  } catch (e) {}

  // Load creds
  try {
    const creds = await window.kt.getCredentials();
    if (creds.nous) {
      el.nousApiKey.value = creds.nous.apiKey || '';
      setNousModelValue(creds.nous.model || 'tencent/hy3:free');
    } else if (creds.nouse) {
      el.nousApiKey.value = creds.nouse.apiKey || '';
      setNousModelValue(creds.nouse.model || 'tencent/hy3:free');
    }
    if (creds.blofin) {
      el.blofinApiKey.value = creds.blofin.apiKey || '';
      el.blofinSecretKey.value = creds.blofin.secretKey || '';
      el.blofinPassphrase.value = creds.blofin.passphrase || '';
      if (el.blofinDemoMode) el.blofinDemoMode.checked = !!creds.blofin.demoMode;
    }
  } catch (e) {}

  // Compendium path
  try {
    const p = await window.kt.getCompendiumPath();
    el.compendiumPathDisplay.textContent = p;
  } catch (e) {}

  // Hermes sandboxed home path
  try {
    const h = await window.kt.getHermesHome();
    if (el.hermesHomeDisplay) el.hermesHomeDisplay.textContent = h;
  } catch (e) {}

  try { syncWebviewParking('setup'); } catch (_) {}

  // Load existing logs
  try {
    const logs = await window.kt.getLogs();
    logs.forEach(appendLogLine);
  } catch (e) {}

  // Check hermes install
  checkHermesStatus();

  // Check dashboard status — only restore UI if gateway is actually ready.
  // A leftover listener on 9119 used to hide the start button forever.
  try {
    const ds = await window.kt.getDashboardStatus();
    if (ds.ready && ds.gatewayRunning) {
      setDashboardState(true, true, true);
      loadDashboard(ds.url || 'http://127.0.0.1:9119');
    } else {
      setDashboardState(false, false);
    }
  } catch (e) {}

  // Live events
  window.kt.onLogLine((entry) => {
    appendLogLine(entry);
    if (currentTab !== 'logs') { newLogs++; updateLogBadge(); }
  });

  window.kt.onDashboardReady((d) => {
    setDashboardState(true, true, d.gatewayRunning);
    loadDashboard(d.url);
  });

  window.kt.onDashboardStopped(() => {
    setDashboardState(false, false);
  });

  updateNousTestButton();
  updateBlofinTestButton();
}

// ── Hermes install check ──────────────────────────────────────
async function checkHermesStatus() {
  el.hermesInstallStatus.textContent = 'Checking...';
  try {
    const result = await window.kt.checkHermes();
    hermesInstalled = result.installed;
    if (result.installed) {
      el.hermesInstallStatus.textContent = '✓ Installed';
      el.hermesInstallStatus.style.color = 'var(--good)';
      el.hermesVersionTag.textContent = result.version;
      el.hermesVersionTag.classList.remove('hidden');
      el.btnInstallHermes.textContent = '✓ Already Installed';
      el.btnInstallHermes.disabled = true;
      el.aboutHermesVer.textContent = result.version;
    } else if (result.partial) {
      el.hermesInstallStatus.textContent = '⚠ Partial install — click Install to resume';
      el.hermesInstallStatus.style.color = 'var(--warn)';
      el.btnInstallHermes.textContent = 'Resume Hermes Install';
      el.btnInstallHermes.disabled = false;
      el.aboutHermesVer.textContent = 'Partial install';
    } else {
      el.hermesInstallStatus.textContent = '✗ Not installed';
      el.hermesInstallStatus.style.color = 'var(--error)';
      el.btnInstallHermes.disabled = false;
      el.hermesNavBadge.classList.remove('hidden');
      el.aboutHermesVer.textContent = 'Not installed';
    }
  } catch (e) {
    el.hermesInstallStatus.textContent = 'Check failed';
  }
}

// ── Dashboard state ───────────────────────────────────────────
function setDashboardState(running, ready, gatewayRunning) {
  dashboardRunning = !!(running && ready);
  el.btnStartDashboard.classList.toggle('hidden', running && ready);
  el.btnStartDashboard.disabled = dashboardStartInFlight;
  el.btnStopDashboard.classList.toggle('hidden', !running);
  el.statusPill.classList.toggle('running', running && ready);
  el.statusLabel.textContent = running ? (ready ? 'Running' : 'Starting…') : 'Stopped';

  if (ready) {
    el.dashboardStatus.textContent = gatewayRunning === false
      ? '✓ Dashboard ready — starting gateway…'
      : '✓ Dashboard + gateway ready — cron can fire';
    el.dashboardStatus.style.color = 'var(--good)';
    el.btnConfigureCron.disabled = false;
    el.dashboardEmbedWrap.classList.remove('hidden');
  } else if (running) {
    el.dashboardStatus.textContent = '⏳ Starting dashboard + gateway…';
    el.dashboardStatus.style.color = 'var(--accent)';
    el.btnConfigureCron.disabled = true;
  } else {
    el.dashboardStatus.textContent = 'Not running';
    el.dashboardStatus.style.color = 'var(--text3)';
    el.btnConfigureCron.disabled = true;
    el.dashboardEmbedWrap.classList.add('hidden');
  }
}

async function startHermesDashboardUi() {
  if (dashboardStartInFlight) return;
  dashboardStartInFlight = true;
  setDashboardState(true, false);
  el.dashboardStatus.textContent = '⏳ Starting dashboard + gateway…';
  el.dashboardStatus.style.color = 'var(--accent)';
  try {
    const result = await window.kt.startDashboard();
    if (!result.ok) {
      setDashboardState(false, false);
      el.dashboardStatus.textContent = '✗ ' + (result.msg || result.error || 'Failed to start');
      el.dashboardStatus.style.color = 'var(--error)';
      return;
    }
    setDashboardState(true, true, !!result.gatewayRunning);
    loadDashboard(result.url || 'http://127.0.0.1:9119');
  } catch (e) {
    setDashboardState(false, false);
    el.dashboardStatus.textContent = '✗ ' + (e.message || 'Failed to start');
    el.dashboardStatus.style.color = 'var(--error)';
  } finally {
    dashboardStartInFlight = false;
    el.btnStartDashboard.disabled = false;
  }
}

function loadDashboard(url) {
  el.dashUrl.textContent = url;
  el.hermesWebview.src = url;
}

// ── Credentials save ──────────────────────────────────────────
async function saveAndWriteCompendium() {
  const data = {
    nous: {
      apiKey: el.nousApiKey.value.trim(),
      model: el.nousModel.value
    },
    blofin: {
      apiKey: el.blofinApiKey.value.trim(),
      secretKey: el.blofinSecretKey.value.trim(),
      passphrase: el.blofinPassphrase.value.trim(),
      demoMode: !!(el.blofinDemoMode && el.blofinDemoMode.checked)
    }
  };
  try {
    await window.kt.saveCredentials(data);
    const comp = await window.kt.writeCompendium();
    if (comp.ok) {
      showSaveStatus('✓ Saved & compendium written', false);
      el.compendiumStatus.classList.remove('hidden');
    } else {
      showSaveStatus('Saved (compendium failed: ' + comp.error + ')', true);
    }
    if (tradingLoaded) {
      window.kt.startTradingDashboard().catch(() => {});
    }
  } catch (e) {
    showSaveStatus('✗ Error: ' + e.message, true);
  }
}

function showSaveStatus(msg, err) {
  el.saveStatus.textContent = msg;
  el.saveStatus.classList.toggle('error', err);
  el.saveStatus.classList.add('show');
  setTimeout(() => el.saveStatus.classList.remove('show'), 3000);
}

function updateNousTestButton() {
  const ready = el.nousApiKey.value.trim().length > 0 && el.nousModel.value.trim().length > 0;
  el.btnTestNous.disabled = !ready;
}

function setNousTestStatus(msg, state) {
  el.nousTestStatus.textContent = msg;
  el.nousTestStatus.className = 'nous-test-status' + (state ? ` ${state}` : '');
}

function setCredFilePath(span, filePath) {
  if (!span) return;
  if (!filePath) {
    span.textContent = '';
    span.classList.remove('loaded');
    return;
  }
  span.textContent = filePath;
  span.classList.add('loaded');
}

function setNousModelValue(model) {
  if (!model || !el.nousModel) return;
  const exists = [...el.nousModel.options].some((opt) => opt.value === model);
  if (!exists) {
    const opt = document.createElement('option');
    opt.value = model;
    opt.textContent = `${model} (from file)`;
    el.nousModel.insertBefore(opt, el.nousModel.firstChild);
  }
  el.nousModel.value = model;
}

function applyNousFromFile(data) {
  if (data.apiKey) el.nousApiKey.value = data.apiKey;
  if (data.model) setNousModelValue(data.model);
  updateNousTestButton();
  setNousTestStatus('', '');
}

function applyBlofinFromFile(data) {
  if (data.apiKey) el.blofinApiKey.value = data.apiKey;
  if (data.secretKey) el.blofinSecretKey.value = data.secretKey;
  if (data.passphrase) el.blofinPassphrase.value = data.passphrase;
  if (el.blofinDemoMode && data.demoMode != null) el.blofinDemoMode.checked = !!data.demoMode;
  updateBlofinTestButton();
  setBlofinTestStatus('', '');
}

function updateBlofinTestButton() {
  const ready = el.blofinApiKey.value.trim().length > 0
    && el.blofinSecretKey.value.trim().length > 0
    && el.blofinPassphrase.value.trim().length > 0;
  el.btnTestBlofin.disabled = !ready;
}

function setBlofinTestStatus(msg, state) {
  el.blofinTestStatus.textContent = msg;
  el.blofinTestStatus.className = 'nous-test-status' + (state ? ` ${state}` : '');
}

// ── Logs ─────────────────────────────────────────────────────
function appendLogLine(entry) {
  el.logEmpty.style.display = 'none';
  const d = document.createElement('div');
  d.className = `log-line ${entry.type || 'info'}`;
  const ts = new Date(entry.ts).toTimeString().slice(0, 8);
  d.innerHTML = `<span class="log-ts">${ts}</span><span class="log-msg">${esc(entry.msg)}</span>`;
  el.logList.appendChild(d);
  if (autoScroll) el.logContainer.scrollTop = el.logContainer.scrollHeight;
}

function esc(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function updateLogBadge() {
  if (newLogs > 0) {
    el.logBadge.textContent = newLogs > 99 ? '99+' : newLogs;
    el.logBadge.classList.remove('hidden');
  } else {
    el.logBadge.classList.add('hidden');
  }
}

let tradingLoaded = false;
let tradingPreloadPath = '';
let tradingInitPromise = null;

function setTradingStatus(text, state) {
  const statusEl = document.getElementById('trading-dashboard-status');
  const activityEl = document.getElementById('trading-activity-status');
  if (statusEl) statusEl.textContent = text || 'Not loaded yet';
  if (statusEl) statusEl.className = 'monitor-value' + (state ? ` ${state}` : '');
}

function setTradingActivity(text) {
  const el = document.getElementById('trading-activity-status');
  if (el) el.textContent = text || 'Waiting for Hermes';
}

function showTradingError(message) {
  if (!message) return;
  try {
    appendLogLine({ ts: Date.now(), type: 'warn', msg: `[Trading] ${String(message)}` });
  } catch (_) {}
  setTradingStatus('Load failed', 'error');
}

function guestHasPage(webview) {
  if (!webview) return false;
  const src = String(webview.getAttribute('src') || webview.src || '');
  return !!src && src !== 'about:blank';
}

function parkWebview(webview, parked) {
  if (!webview) return;
  try {
    webview.classList.toggle('webview-parked', !!parked);
  } catch (_) {}
  if (parked || !guestHasPage(webview)) return;
  try {
    webview.executeJavaScript('window.dispatchEvent(new Event("resize"))').catch(() => {});
  } catch (_) {}
}

function syncWebviewParking(activeTab) {
  parkWebview(el.tradingWebview, activeTab !== 'trading');
  parkWebview(el.hermesWebview, activeTab !== 'hermes');
}

function attachTradingGuest(webview) {
  if (!webview) return;
  try {
    const wcId = webview.getWebContentsId();
    window.kt.attachTradingWebview(wcId).catch((e) => console.warn('attachTradingWebview:', e));
  } catch (e) {
    console.warn('attachTradingWebview:', e);
  }
}

function bindTradingWebview(webview) {
  if (!webview || webview.dataset.bound === '1') return webview;
  webview.dataset.bound = '1';
  webview.addEventListener('did-attach', () => attachTradingGuest(webview));
  webview.addEventListener('dom-ready', () => {
    attachTradingGuest(webview);
    parkWebview(webview, currentTab !== 'trading');
  });
  webview.addEventListener('did-finish-load', async () => {
    try {
      const s = await window.kt.getTradingStatus();
      if (s?.sseConnected) {
        setTradingStatus('Live · SSE connected', 'ok');
        setTradingActivity('Signal connected');
      } else {
        setTradingStatus('Live', 'pending');
        setTradingActivity('Waiting for signal snapshot');
      }
    } catch (_) {
      setTradingStatus('Live', 'pending');
      setTradingActivity('Waiting for signal snapshot');
    }
  });
  webview.addEventListener('did-fail-load', (e) => {
    if (e.errorCode === -3) return;
    const reason = e.errorDescription || `Failed to load trading desk (${e.errorCode})`;
    setTradingStatus('Load failed', 'error');
    setTradingActivity('Check Hermes dashboard');
    showTradingError(`${reason}. If trading desk is unavailable, open the Hermes Dashboard in the Hermes tab.`);
  });
  webview.addEventListener('console-message', (e) => {
    if (e.level >= 2 && /unexpected token|chrome is not defined/i.test(e.message || '')) {
      setTradingStatus('Desk error', 'error');
      setTradingActivity('Check Hermes dashboard');
      const where = [e.sourceId, Number.isFinite(e.line) ? `:${e.line}` : ''].join('');
      showTradingError(`${e.message}${where ? ` (${where})` : ''}. If the trading desk cannot load, use the Hermes tab dashboard.`);
    }
  });
  return webview;
}

function ensureTradingWebview(preloadPath) {
  const wrap = el.tradingWebviewWrap;
  if (!wrap) return null;
  const preload = String(preloadPath || '').trim();
  let webview = el.tradingWebview;
  if (webview && (!preload || webview.getAttribute('preload') === preload)) {
    return bindTradingWebview(webview);
  }

  const next = document.createElement('webview');
  next.id = 'trading-webview';
  if (preload) next.setAttribute('preload', preload);
  next.setAttribute('partition', 'persist:blohunter-trading');
  next.setAttribute('allowpopups', '');
  next.setAttribute('webpreferences', 'contextIsolation=yes, nodeIntegration=no');
  if (webview) webview.replaceWith(next);
  else wrap.appendChild(next);
  el.tradingWebview = next;
  return bindTradingWebview(next);
}

function withTimeout(promise, ms, message) {
  let timer;
  return Promise.race([
    Promise.resolve(promise).finally(() => clearTimeout(timer)),
    new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(message)), ms);
    }),
  ]);
}

// ── Tab switching ─────────────────────────────────────────────
function switchTab(name) {
  currentTab = name;
  el.navItems.forEach(i => i.classList.toggle('active', i.dataset.tab === name));
  el.tabPanels.forEach(p => p.classList.toggle('active', p.id === `tab-${name}`));
  try { syncWebviewParking(name); } catch (_) {}
  if (name === 'logs') { newLogs = 0; updateLogBadge(); }
  if (name === 'trading') initTradingTab();
  if (name === 'hermes' && hermesInstalled && !dashboardRunning && !dashboardStartInFlight) {
    startHermesDashboardUi();
  }
}

async function loadTradingDesk(forceReload = false) {
  if (!tradingPreloadPath) {
    tradingPreloadPath = await window.kt.getBlohunterPreloadPath();
  }
  const webview = ensureTradingWebview(tradingPreloadPath);
  if (!webview) return;

  parkWebview(webview, false);

  const result = await withTimeout(
    window.kt.startTradingDashboard(),
    90000,
    'Trading desk startup timed out. Check Logs, then click Reload.'
  );
  if (!result?.ok || !result.url) return;

  const nextUrl = forceReload ? `${result.url}${result.url.includes('?') ? '&' : '?'}t=${Date.now()}` : result.url;
  if (webview.src !== nextUrl) webview.src = nextUrl;
  tradingLoaded = true;
}

async function initTradingTab() {
  if (tradingInitPromise) return tradingInitPromise;
  if (tradingLoaded && guestHasPage(el.tradingWebview)) {
    parkWebview(el.tradingWebview, false);
    tradingInitPromise = (async () => {
      try { await window.kt.startTradingDashboard(); } catch (_) {}
      finally { tradingInitPromise = null; }
    })();
    return tradingInitPromise;
  }

  tradingInitPromise = (async () => {
    try { await loadTradingDesk(false); } catch (_) {}
    finally { tradingInitPromise = null; }
  })();

  return tradingInitPromise;
}

function handleTrayRestore() {
  try {
    if (!currentTab || currentTab === 'trading') {
      if (guestHasPage(el.tradingWebview)) {
        loadTradingDesk(true).catch(() => {});
      } else {
        initTradingTab();
      }
    }
  } catch (_) {}
}

if (window.kt?.onLogLine) {
  window.kt.onLogLine(() => {});
}

if (window.kt?.onUpdateError) {
  window.kt.onUpdateError(() => {});
}

try {
  if (window.ipcRenderer?.on) {
    window.ipcRenderer.on('kt-restore-trading-webview', handleTrayRestore);
  }
} catch (_) {}

if (el.btnReloadTrading) {
  el.btnReloadTrading.addEventListener('click', () => loadTradingDesk(true).catch(() => {}));
}

// ── Event listeners ───────────────────────────────────────────
if (el.minimize) el.minimize.addEventListener('click', () => window.kt.minimize());
if (el.maximize) el.maximize.addEventListener('click', () => window.kt.maximize());
if (el.close) el.close.addEventListener('click', () => window.kt.close());

el.navItems.forEach(item => item.addEventListener('click', () => switchTab(item.dataset.tab)));

// Setup form
el.formSetup.addEventListener('submit', async (e) => {
  e.preventDefault();
  el.btnSave.disabled = true;
  await saveAndWriteCompendium();
  el.btnSave.disabled = false;
});

// Password toggles
document.querySelectorAll('.toggle-vis').forEach(btn => {
  btn.addEventListener('click', () => {
    const inp = document.getElementById(btn.dataset.target);
    if (inp) inp.type = inp.type === 'password' ? 'text' : 'password';
  });
});

el.nousApiKey.addEventListener('input', () => {
  updateNousTestButton();
  setNousTestStatus('', '');
});
el.nousModel.addEventListener('change', () => {
  updateNousTestButton();
  setNousTestStatus('', '');
});

el.btnLoadNousFile.addEventListener('click', async () => {
  el.btnLoadNousFile.disabled = true;
  try {
    const result = await window.kt.pickNousCredentialFile();
    if (result.cancelled) return;
    if (!result.ok) {
      setNousTestStatus(`✗ ${result.error || 'Could not load file'}`, 'error');
      return;
    }
    applyNousFromFile(result.nous);
    setCredFilePath(el.nousFilePath, result.path);
  } catch (e) {
    setNousTestStatus(`✗ ${e.message}`, 'error');
  } finally {
    el.btnLoadNousFile.disabled = false;
  }
});

el.btnLoadBlofinFile.addEventListener('click', async () => {
  el.btnLoadBlofinFile.disabled = true;
  try {
    const result = await window.kt.pickBlofinCredentialFile();
    if (result.cancelled) return;
    if (!result.ok) {
      setBlofinTestStatus(`✗ ${result.error || 'Could not load file'}`, 'error');
      return;
    }
    applyBlofinFromFile(result.blofin);
    setCredFilePath(el.blofinFilePath, result.path);
  } catch (e) {
    setBlofinTestStatus(`✗ ${e.message}`, 'error');
  } finally {
    el.btnLoadBlofinFile.disabled = false;
  }
});

el.btnTestNous.addEventListener('click', async () => {
  const apiKey = el.nousApiKey.value.trim();
  const model = el.nousModel.value;
  if (!apiKey || !model) return;

  el.btnTestNous.disabled = true;
  setNousTestStatus('Testing…', 'pending');
  try {
    const result = await window.kt.testNousCredentials({ apiKey, model });
    if (result.ok) {
      const preview = result.reply ? ` — "${result.reply.slice(0, 60)}"` : '';
      setNousTestStatus(`✓ Connected to ${result.model}${preview}`, 'ok');
    } else {
      setNousTestStatus(`✗ ${result.error || 'Test failed'}`, 'error');
    }
  } catch (e) {
    setNousTestStatus(`✗ ${e.message}`, 'error');
  } finally {
    updateNousTestButton();
  }
});

function bindBlofinTestInputs() {
  const reset = () => {
    updateBlofinTestButton();
    setBlofinTestStatus('', '');
  };
  el.blofinApiKey.addEventListener('input', reset);
  el.blofinSecretKey.addEventListener('input', reset);
  el.blofinPassphrase.addEventListener('input', reset);
  if (el.blofinDemoMode) el.blofinDemoMode.addEventListener('change', reset);
}
bindBlofinTestInputs();

el.btnTestBlofin.addEventListener('click', async () => {
  const creds = {
    apiKey: el.blofinApiKey.value.trim(),
    secretKey: el.blofinSecretKey.value.trim(),
    passphrase: el.blofinPassphrase.value.trim(),
    demoMode: !!(el.blofinDemoMode && el.blofinDemoMode.checked),
  };
  if (!creds.apiKey || !creds.secretKey || !creds.passphrase) return;

  el.btnTestBlofin.disabled = true;
  setBlofinTestStatus('Testing…', 'pending');
  try {
    const result = await window.kt.testBlofinCredentials(creds);
    if (result.ok) {
      setBlofinTestStatus(`✓ ${result.mode} connected — ${result.summary}`, 'ok');
    } else {
      setBlofinTestStatus(`✗ ${result.error || 'Test failed'}`, 'error');
    }
  } catch (e) {
    setBlofinTestStatus(`✗ ${e.message}`, 'error');
  } finally {
    updateBlofinTestButton();
  }
});

// Defender exclusion (Step 0)
const btnAddExclusion    = $('btn-add-exclusion');
const exclusionStatus    = $('exclusion-status');
const exclusionManual    = $('exclusion-manual');
const exclusionPathDisp  = $('exclusion-path-display');

btnAddExclusion.addEventListener('click', async () => {
  btnAddExclusion.disabled = true;
  exclusionStatus.textContent = '⏳ Adding exclusion… (approve the UAC prompt)';
  exclusionStatus.style.color = 'var(--accent)';
  const res = await window.kt.addDefenderExclusion();
  if (res.ok) {
    exclusionStatus.textContent = '✅ Exclusion added — now safe to install';
    exclusionStatus.style.color = 'var(--good)';
  } else {
    exclusionStatus.textContent = '⚠ Failed — add manually (see below)';
    exclusionStatus.style.color = 'var(--warn)';
    exclusionManual.classList.remove('hidden');
    if (res.manual && exclusionPathDisp) exclusionPathDisp.textContent = res.manual;
    btnAddExclusion.disabled = false;
  }
});

// Hermes install
el.btnInstallHermes.addEventListener('click', async () => {
  el.btnInstallHermes.disabled = true;
  el.hermesInstallStatus.textContent = '⏳ Installing Hermes, then starting dashboard…';
  el.hermesInstallStatus.style.color = 'var(--accent)';
  switchTab('logs');
  const result = await window.kt.installHermes();
  if (result.ok) {
    hermesInstalled = true;
    el.hermesInstallStatus.textContent = '✓ Installed: ' + result.version;
    el.hermesInstallStatus.style.color = 'var(--good)';
    el.hermesNavBadge.classList.add('hidden');
    el.btnInstallHermes.textContent = '✓ Already Installed';
    try {
      const ds = await window.kt.getDashboardStatus();
      if (ds.running || ds.ready) {
        setDashboardState(!!ds.running, !!ds.ready, !!ds.gatewayRunning);
        if (ds.ready) loadDashboard(ds.url || 'http://127.0.0.1:9119');
      }
    } catch (e) {}
  } else if (result.partial) {
    el.hermesInstallStatus.textContent = '⚠ Partial install — click Install to resume (see Logs)';
    el.hermesInstallStatus.style.color = 'var(--warn)';
    el.btnInstallHermes.textContent = 'Resume Hermes Install';
    el.btnInstallHermes.disabled = false;
  } else {
    el.hermesInstallStatus.textContent = '✗ Install failed — check Logs tab';
    el.hermesInstallStatus.style.color = 'var(--error)';
    el.btnInstallHermes.disabled = false;
  }
});

// Write compendium
el.btnWriteCompendium.addEventListener('click', async () => {
  const res = await window.kt.writeCompendium();
  if (res.ok) {
    el.compendiumStatus.textContent = '✓ Written to: ' + res.path;
    el.compendiumStatus.classList.remove('hidden');
    el.compendiumStatus.style.color = 'var(--good)';
  } else {
    el.compendiumStatus.textContent = '✗ ' + res.error;
    el.compendiumStatus.classList.remove('hidden');
    el.compendiumStatus.style.color = 'var(--error)';
  }
});

// Start / stop dashboard
el.btnStartDashboard.addEventListener('click', () => startHermesDashboardUi());

el.btnStopDashboard.addEventListener('click', async () => {
  await window.kt.stopDashboard();
  setDashboardState(false, false);
});

// Configure cron
el.btnConfigureCron.addEventListener('click', async () => {
  el.btnConfigureCron.disabled = true;
  el.cronStatus.textContent = '⏳ Configuring…';
  el.cronStatus.style.color = 'var(--accent)';
  const result = await window.kt.configureCron();
  if (result.ok) {
    el.cronStatus.textContent = result.updated
      ? '✅ Cron updated — every 5 minutes!'
      : '✅ Cron active — every 5 minutes!';
    el.cronStatus.style.color = 'var(--good)';
    el.manualPromptWrap.classList.add('hidden');
  } else {
    el.cronStatus.textContent = result.msg ? `⚠ ${result.msg}` : '⚠ Manual setup needed';
    el.cronStatus.style.color = 'var(--warn)';
    const prompt = result.prompt || await window.kt.getCronPrompt();
    el.cronPromptText.textContent = prompt;
    el.manualPromptWrap.classList.remove('hidden');
    el.btnConfigureCron.disabled = false;
  }
});

// Copy prompt
el.btnCopyPrompt.addEventListener('click', () => {
  navigator.clipboard.writeText(el.cronPromptText.textContent).then(() => {
    el.btnCopyPrompt.textContent = '✓ Copied!';
    setTimeout(() => el.btnCopyPrompt.textContent = 'Copy Prompt', 2000);
  });
});

// Dashboard controls
el.btnReloadDash.addEventListener('click', () => { el.hermesWebview.reload(); });
el.btnOpenDashExternal.addEventListener('click', () => window.kt.openExternal('http://127.0.0.1:9119'));

// Autoscroll toggle
el.btnAutoscroll.addEventListener('click', () => {
  autoScroll = !autoScroll;
  el.btnAutoscroll.classList.toggle('active', autoScroll);
});

// Clear logs
el.btnClearLogs.addEventListener('click', async () => {
  await window.kt.clearLogs();
  el.logList.innerHTML = '';
  el.logEmpty.style.display = '';
});

// Log scroll pause
el.logContainer.addEventListener('scroll', () => {
  const atBottom = el.logContainer.scrollHeight - el.logContainer.scrollTop <= el.logContainer.clientHeight + 40;
  if (!atBottom && autoScroll) { autoScroll = false; el.btnAutoscroll.classList.remove('active'); }
});

// Quick links
const NOUS_PORTAL_URL = 'https://portal.nousresearch.com/manage-subscription';

const LINKS = {
  'link-blofin-dashboard': 'https://blofin.com/futures',
  'link-blofin-api-page': 'https://blofin.com/account/api',
  'link-nous-portal-settings': NOUS_PORTAL_URL,
  'link-hermes-dashboard': 'http://127.0.0.1:9119',
  'link-hermes-docs': 'https://hermes-agent.nousresearch.com/docs/integrations/nous-portal',
  'link-nous-portal': NOUS_PORTAL_URL,
  'link-blofin-api': 'https://blofin.com/account/api',
  'btn-open-blofin': 'https://blofin.com/futures'
};
Object.entries(LINKS).forEach(([id, url]) => {
  const elem = document.getElementById(id);
  if (elem) elem.addEventListener('click', (e) => { e.preventDefault(); window.kt.openExternal(url); });
});

// ── Update banner ───────────────────────────────────────────────
function setUpdateBannerVisible(visible, title, text) {
  if (!el.updateBanner) return;
  el.updateBanner.classList.toggle('hidden', !visible);
  if (title && el.updateBannerTitle) el.updateBannerTitle.textContent = title;
  if (text && el.updateBannerText) el.updateBannerText.textContent = text;
}

if (el.btnRestartUpdate) {
  el.btnRestartUpdate.addEventListener('click', () => {
    window.kt.quitAndInstallUpdate().catch(() => {});
  });
}
if (el.btnDismissUpdate) {
  el.btnDismissUpdate.addEventListener('click', () => {
    setUpdateBannerVisible(false);
  });
}

window.kt.onUpdateAvailable((info) => {
  setUpdateBannerVisible(true, 'Update available', 'Restart to install the latest version.');
  if (el.popupUpdateStatus) el.popupUpdateStatus.textContent = 'Update available — restart to install';
});
window.kt.onUpdateNotAvailable((info) => {
  if (el.popupUpdateStatus) el.popupUpdateStatus.textContent = 'You’re on the latest version';
});
window.kt.onUpdateDownloaded((info) => {
  setUpdateBannerVisible(true, 'Update ready', 'Restart to apply the latest version.');
  if (el.popupUpdateStatus) el.popupUpdateStatus.textContent = 'Update ready — restart to install';
});
window.kt.onUpdateError((error) => {
  const msg = error?.message || String(error || 'Update failed');
  if (el.popupUpdateStatus) el.popupUpdateStatus.textContent = msg;
});

// ── Update popup menu ───────────────────────────────────────────
function setPopupOpen(open) {
  if (!el.popupLauncher || !el.popupMenu) return;
  el.popupMenu.classList.toggle('hidden', !open);
  if (el.btnPopupTrigger) el.btnPopupTrigger.setAttribute('aria-expanded', String(open));
}

function togglePopupMenu() {
  if (!el.popupLauncher || !el.popupMenu) return;
  const isHidden = el.popupMenu.classList.contains('hidden');
  setPopupOpen(isHidden);
}

if (el.btnPopupTrigger) {
  el.btnPopupTrigger.addEventListener('click', (e) => {
    e.stopPropagation();
    togglePopupMenu();
  });
}

if (el.popupLauncher) {
  el.popupLauncher.addEventListener('click', (e) => {
    e.stopPropagation();
  });
}

document.addEventListener('click', (e) => {
  if (!el.popupMenu?.classList.contains('hidden')) {
    const inside = el.popupLauncher?.contains(e.target);
    if (!inside) setPopupOpen(false);
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && el.popupMenu && !el.popupMenu.classList.contains('hidden')) {
    setPopupOpen(false);
  }
});

async function checkForUpdatesFromMenu() {
  if (el.popupUpdateStatus) {
    el.popupUpdateStatus.textContent = 'Checking for updates…';
  }
  if (el.btnCheckForUpdates) {
    el.btnCheckForUpdates.disabled = true;
  }
  try {
    await window.kt.checkForUpdates();
  } catch (e) {
    const msg = e?.message || 'Update check failed';
    if (el.popupUpdateStatus) el.popupUpdateStatus.textContent = msg;
  } finally {
    if (el.btnCheckForUpdates) el.btnCheckForUpdates.disabled = false;
  }
}

if (el.btnCheckForUpdates) {
  el.btnCheckForUpdates.addEventListener('click', checkForUpdatesFromMenu);
}

if (el.btnForgot) {
  el.btnForgot.addEventListener('click', () => showForgotForm());
}
if (el.btnForgotBack) {
  el.btnForgotBack.addEventListener('click', () => showLoginForm());
}
if (el.formLogin) {
  el.formLogin.addEventListener('submit', handleLoginSubmit);
}
if (el.formForgot) {
  el.formForgot.addEventListener('submit', handleForgotSubmit);
}
if (window.kt?.onSubscriptionLocked) {
  window.kt.onSubscriptionLocked((status) => applySubscriptionLock(status));
}

async function refreshMembershipUi() {
  try {
    const status = await window.kt.authSubscriptionStatus();
    const statusEl = document.getElementById('membership-status');
    const emailEl = document.getElementById('membership-email');
    if (statusEl) statusEl.textContent = status?.status === 'active' ? 'Active' : 'Inactive';
    if (emailEl && status?.email) emailEl.textContent = status.email;
  } catch {}
}

if (document.getElementById('btn-renew-membership')) {
  document.getElementById('btn-renew-membership').addEventListener('click', openStripeCheckout);
}
if (document.getElementById('btn-auth-logout')) {
  document.getElementById('btn-auth-logout').addEventListener('click', async () => {
    await window.kt.authLogout();
    authReady = false;
    hideLoginOverlay();
    showLoginForm();
  });
}

// Lock overlay buttons
const btnLockRenew = document.getElementById('btn-lock-renew');
const btnLockRecheck = document.getElementById('btn-lock-recheck');
const btnLockSignout = document.getElementById('btn-lock-signout');
const lockMessage = document.getElementById('lock-message');

if (btnLockRenew) {
  btnLockRenew.addEventListener('click', async () => {
    try {
      const result = await window.kt.authCreateCheckoutSession();
      if (result?.ok && result.url) {
        window.kt.openExternal(result.url);
      } else {
        if (lockMessage) lockMessage.textContent = result?.msg || 'Could not open checkout.';
      }
    } catch (e) {
      if (lockMessage) lockMessage.textContent = 'Could not open checkout.';
    }
  });
}
if (btnLockRecheck) {
  btnLockRecheck.addEventListener('click', async () => {
    if (btnLockRecheck) btnLockRecheck.disabled = true;
    if (lockMessage) lockMessage.textContent = 'Rechecking...';
    try {
      const status = await window.kt.authSubscriptionStatus();
      if (status?.status === 'active') {
        hideSubscriptionLock();
        hideLoginOverlay();
        authReady = true;
        if (lockMessage) lockMessage.textContent = '';
      } else {
        if (lockMessage) lockMessage.textContent = status?.msg || 'Membership is still not active.';
      }
    } catch (e) {
      if (lockMessage) lockMessage.textContent = 'Recheck failed. Try again.';
    } finally {
      if (btnLockRecheck) btnLockRecheck.disabled = false;
    }
  });
}
if (btnLockSignout) {
  btnLockSignout.addEventListener('click', async () => {
    await window.kt.authLogout();
    authReady = false;
    hideSubscriptionLock();
    showLoginForm();
  });
}

// ── VPN helper ───────────────────────────────────────────────
function setVpnStatus(message, state) {
  if (!el.vpnStatus) return;
  el.vpnStatus.textContent = message || '';
  el.vpnStatus.className = 'step-status' + (state ? ` ${state}` : '');
}

function openVpnGuide() {
  const guideUrl = 'https://protonvpn.com/free-vpn';
  const country = el.vpnCountry?.value || 'random';
  const isRandom = country === 'random';
  const countryLabel = isRandom ? 'an allowed country' : `country code ${country}`;
  const note = isRandom
    ? ''
    : ` Selected preferred exit: ${countryLabel}.`;
  setVpnStatus(`Opening ProtonVPN guide for ${countryLabel}.${note}`, '');
  window.kt.openExternal(guideUrl).catch(() => {});
}

if (el.btnVpnGuide) {
  el.btnVpnGuide.addEventListener('click', () => openVpnGuide());
}

if (el.navItems) {
  el.navItems.forEach((item) => item.addEventListener('click', () => {
    if (item.dataset.tab === 'hermes' && el.vpnStatus && !el.vpnStatus.textContent.trim()) {
      setVpnStatus('Use the Proton VPN helper below for free retry guidance.', '');
    }
  }));
}

// ── Boot ─────────────────────────────────────────────────────
// NOTE: classic <script> (no type="module") — top-level `await` is a
// SyntaxError in browsers and would kill the whole file, leaving every
// button / tab dead. init() must run inside an async IIFE instead.
(async () => {
  try {
    await init();
  } catch (e) {
    // Make sure the user sees a fatal error instead of a dead UI.
    console.error('[KnightTrader] init failed:', e);
    try {
      if (document.body) {
        const bail = document.createElement('pre');
        bail.style.cssText = 'position:fixed;inset:0;background:#0b0d10;color:#ff7b72;font:14px/1.4 monospace;padding:12px;overflow:auto;z-index:9999';
        bail.textContent = `[KnightTrader] init failed:\n${e && (e.stack || e)}`;
        document.body.appendChild(bail);
      }
    } catch {}
  }
})();
