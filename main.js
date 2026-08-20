const { app, BrowserWindow, ipcMain, shell, dialog, protocol, webContents, session, Tray, nativeImage, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');
const { BlohunterBridge } = require('./blohunter-bridge');
const { spawn, execFileSync } = require('child_process');
const crypto = require('crypto');
const http = require('http');
const https = require('https');
const os = require('os');
const { autoUpdater } = require('electron-updater');

const BLOHUNTER_SRC = path.join(os.homedir(), 'Downloads', 'blohunter-connect', 'src');
let blohunterWatcherReady = false;
let blohunterHotReloadTimer = null;

protocol.registerSchemesAsPrivileged([
  {
    scheme: 'bh',
    privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true },
  },
]);

function broadcastHotReload(channels = ['blohunter-hot-reload']) {
  for (const wc of webContents.getAllWebContents()) {
    for (const channel of channels) wc.send(channel);
  }
}

function startBlohunterHotReloadWatcher() {
  if (blohunterWatcherReady || !fs.existsSync(BLOHUNTER_SRC)) return;
  blohunterWatcherReady = true;
  appendLog(`⚡ Hot reload watching ${BLOHUNTER_SRC}`, 'info');
  try {
    const watcher = fs.watch(BLOHUNTER_SRC, { recursive: true }, (eventType, file) => {
      if (!file) return;
      const lower = String(file).toLowerCase();
      if (!/\.(html|css|js|json)$/.test(lower)) return;
      clearTimeout(blohunterHotReloadTimer);
      blohunterHotReloadTimer = setTimeout(() => {
        blohunterHotReloadTimer = null;
        appendLog(`🔄 Hot reloading trading desk: ${file}`, 'info');
        broadcastHotReload(['blohunter-hot-reload', 'reload-trading-webview']);
      }, 120);
    });
    watcher.on('error', (err) => appendLog(`⚠ Hot reload watcher failed: ${err.message}`, 'warn'));
  } catch (err) {
    appendLog(`⚠ Hot reload unavailable: ${err.message}`, 'warn');
  }
}

const NOUS_INFERENCE_URL = 'https://inference-api.nousresearch.com/v1/chat/completions';
const NOUS_INFERENCE_BASE = 'https://inference-api.nousresearch.com/v1';
const NOUS_RECOMMENDED_MODELS_URL = 'https://portal.nousresearch.com/api/nous/recommended-models';
const DASHBOARD_PORT = 9119;
const DASHBOARD_PORT_CANDIDATES = [DASHBOARD_PORT, 9120];
const DASHBOARD_PORT_PROBE_TIMEOUT = 1200;
const DASHBOARD_PORT_START_TIMEOUT = 20000;
const GATEWAY_READY_TIMEOUT = 90000;
let activeDashboardPort = null;
function getDashboardBaseUrl(port) {
  return `http://127.0.0.1:${port || activeDashboardPort || DASHBOARD_PORT}`;
}
const DASHBOARD_URL = getDashboardBaseUrl();

// ── Sandboxed Hermes paths (inside app userData — never system-wide) ────────
// All Hermes files live under: <AppData>/Roaming/KnightTrader/hermes/
// HERMES_HOME = that folder
// InstallDir  = HERMES_HOME/hermes-agent   (git clone goes here)
// venv hermes = InstallDir/venv/Scripts/hermes.exe (or .venv on some installs)
const HERMES_HOME    = path.join(app.getPath('userData'), 'hermes');
const HERMES_INSTALL = path.join(HERMES_HOME, 'hermes-agent');
const HERMES_EXE     = path.join(HERMES_INSTALL, 'venv', 'Scripts', 'hermes.exe');

// ── Encrypted credential store ─────────────────────────────────────────────
const STORE_KEY  = Buffer.from('kt-aes256-key-knighttrader-2024!'); // 32 bytes
const STORE_PATH = path.join(app.getPath('userData'), 'kt-config.enc');

function encryptData(obj) {
  const iv  = crypto.randomBytes(16);
  const c   = crypto.createCipheriv('aes-256-cbc', STORE_KEY, iv);
  const enc = Buffer.concat([c.update(JSON.stringify(obj), 'utf8'), c.final()]);
  return JSON.stringify({ iv: iv.toString('hex'), data: enc.toString('hex') });
}
function decryptData(raw) {
  try {
    const { iv, data } = JSON.parse(raw);
    const d = crypto.createDecipheriv('aes-256-cbc', STORE_KEY, Buffer.from(iv, 'hex'));
    return JSON.parse(Buffer.concat([d.update(Buffer.from(data, 'hex')), d.final()]).toString('utf8'));
  } catch { return null; }
}

const BLOFIN_LIVE_URL = 'https://openapi.blofin.com';
const BLOFIN_DEMO_URL = 'https://demo-trading-openapi.blofin.com';

const DEFAULT_NOUS_MODEL = 'tencent/hy3:free';

const FALLBACK_FREE_NOUS_MODELS = [
  { id: 'tencent/hy3:free', label: 'tencent/hy3:free (free)' },
  { id: 'upstage/solar-pro4:free', label: 'upstage/solar-pro4:free (free)' },
  { id: 'meituan/longcat-2.0:free', label: 'meituan/longcat-2.0:free (free)' },
  { id: 'stepfun/step-3.7-flash:free', label: 'stepfun/step-3.7-flash:free (free)' },
  { id: 'poolside/laguna-s-2.1:free', label: 'poolside/laguna-s-2.1:free (free)' },
  { id: 'poolside/laguna-xs-2.1:free', label: 'poolside/laguna-xs-2.1:free (free)' },
];

const FALLBACK_PAID_NOUS_MODELS = [
  { id: 'tencent/hy3', label: 'tencent/hy3' },
  { id: 'moonshotai/kimi-k3', label: 'moonshotai/kimi-k3' },
  { id: 'z-ai/glm-5.2', label: 'z-ai/glm-5.2' },
  { id: 'stepfun/step-3.7-flash', label: 'stepfun/step-3.7-flash' },
  { id: 'meituan/longcat-2.0', label: 'meituan/longcat-2.0' },
  { id: 'upstage/solar-pro4', label: 'upstage/solar-pro4' },
  { id: 'qwen/qwen3.8-max', label: 'qwen/qwen3.8-max' },
  { id: 'minimax/minimax-m2.5', label: 'minimax/minimax-m2.5' },
];

const DEFAULTS = {
  blofin: { apiKey: '', secretKey: '', passphrase: '', demoMode: false },
  nous:   { apiKey: '', model: DEFAULT_NOUS_MODEL },
  settings: { notifySounds: true }
};

const LEGACY_NOUS_MODELS = {
  'hunyuan-turbos-latest': 'tencent/hy3:free',
  'hunyuan-lite': 'tencent/hy3:free',
  'hunyuan-standard': 'tencent/hy3',
  'tencent/hy free': 'tencent/hy3:free',
  'openrouter/elephant-alpha': 'tencent/hy3:free',
  'poolside/laguna-m.1:free': 'poolside/laguna-s-2.1:free',
  'nvidia/nemotron-3-super-120b-a12b:free': 'upstage/solar-pro4:free',
  'nvidia/nemotron-3-ultra-550b-a55b:free': 'meituan/longcat-2.0:free',
  'inclusionai/ring-2.6-1t:free': 'stepfun/step-3.7-flash:free',
  'deepseek/deepseek-v4-flash-free': 'tencent/hy3:free',
};

function normalizeNousModel(model) {
  const m = String(model || '').trim();
  return LEGACY_NOUS_MODELS[m] || m || DEFAULT_NOUS_MODEL;
}

function migrateStoreData(raw) {
  const merged = { ...DEFAULTS, ...raw };
  if (raw?.nouse && !raw?.nous) {
    merged.nous = {
      apiKey: raw.nouse.apiKey || '',
      model: normalizeNousModel(raw.nouse.model),
    };
  } else if (merged.nous) {
    merged.nous = {
      apiKey: merged.nous.apiKey || '',
      model: normalizeNousModel(merged.nous.model),
    };
  }
  delete merged.nouse;
  return merged;
}

function getBlofinBaseUrl() {
  return storeData.blofin.demoMode ? BLOFIN_DEMO_URL : BLOFIN_LIVE_URL;
}

function loadStore() {
  try {
    if (fs.existsSync(STORE_PATH)) {
      const d = decryptData(fs.readFileSync(STORE_PATH, 'utf8'));
      if (d) return migrateStoreData(d);
    }
  } catch {}
  return JSON.parse(JSON.stringify(DEFAULTS));
}
function saveStore(data) {
  try { fs.writeFileSync(STORE_PATH, encryptData(data), 'utf8'); } catch {}
}

let storeData = loadStore();

let blohunterBridge = null;
function getBlohunterBridge() {
  if (!blohunterBridge) {
    blohunterBridge = new BlohunterBridge({
      userDataPath: app.getPath('userData'),
      log: (...args) => appendLog(`[Trading] ${args.map(String).join(' ')}`, 'info'),
    });
  }
  return blohunterBridge;
}

async function syncBlohunterCredentials() {
  const bridge = getBlohunterBridge();
  if (!storeData.blofin?.apiKey) return;
  await bridge.syncCredentials({
    apiKey: storeData.blofin.apiKey,
    secretKey: storeData.blofin.secretKey,
    passphrase: storeData.blofin.passphrase,
    demoMode: storeData.blofin.demoMode,
  });
}

// ── Compendium file ────────────────────────────────────────────────────────
function getCompendiumPath() {
  return path.join(os.homedir(), 'Downloads', 'My Blofin API Compendium.txt');
}
function getHermesEnvPath() {
  return path.join(HERMES_HOME, '.env');
}

function upsertEnvVar(content, key, value) {
  const escapedKey = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const line = `${key}=${value}`;
  const regex = new RegExp(`^${escapedKey}=.*$`, 'm');
  if (regex.test(content)) {
    return content.replace(regex, line);
  }
  const prefix = content.length && !content.endsWith('\n') ? `${content}\n` : content;
  const marker = content.includes('# KnightTrader credential sync') ? '' : '\n# KnightTrader credential sync\n';
  return `${prefix}${marker}${line}\n`;
}

function nodeJsBinDirs() {
  return [
    path.join(process.env.ProgramFiles || 'C:\\Program Files', 'nodejs'),
    path.join(process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)', 'nodejs'),
    path.join(HERMES_INSTALL, 'venv', 'Scripts'),
    path.join(HERMES_INSTALL, 'venv', 'bin'),
  ].filter((dir) => fs.existsSync(dir));
}

function readNousKeyFromEnvFile() {
  try {
    const envPath = getHermesEnvPath();
    if (!fs.existsSync(envPath)) return '';
    const text = fs.readFileSync(envPath, 'utf8');
    const match = text.match(/^NOUS_API_KEY=(.*)$/m) || text.match(/^NOUSRESEARCH_API_KEY=(.*)$/m);
    return (match ? match[1].trim() : '').replace(/^["']|["']$/g, '');
  } catch {
    return '';
  }
}

function resolveNousApiKey() {
  return String(storeData.nous?.apiKey || readNousKeyFromEnvFile() || '').trim();
}

function applyNousKeyToEnv(env) {
  const key = resolveNousApiKey();
  if (!key) {
    delete env.NOUS_API_KEY;
    delete env.NOUSRESEARCH_API_KEY;
    return env;
  }
  env.NOUS_API_KEY = key;
  // Cron jobs with provider:custom + the Nous inference URL look up
  // NOUSRESEARCH_API_KEY (host-derived from inference-api.nousresearch.com),
  // not NOUS_API_KEY. Missing that env var makes Hermes send "no-key-required".
  env.NOUSRESEARCH_API_KEY = key;
  return env;
}

function hermesChildEnv(extra = {}) {
  const env = { ...process.env, ...extra };
  delete env.ELECTRON_RUN_AS_NODE;
  delete env.ELECTRON_NO_ASAR;
  delete env.HERMES_WEB_DIST;
  delete env.HERMES_SERVE_HEADLESS;
  const currentPath = env.PATH || env.Path || '';
  env.PATH = [...nodeJsBinDirs(), currentPath].join(path.delimiter);
  env.Path = env.PATH;
  env.PYTHONUNBUFFERED = '1';
  env.PYTHONIOENCODING = 'utf-8';
  env.HERMES_HOME = HERMES_HOME;
  env.HERMES_DESKTOP = '1';
  return applyNousKeyToEnv(env);
}

function hermesCliEnv() {
  return hermesChildEnv();
}

function syncHermesConfig() {
  const installStatus = checkHermesInstalled();
  if (!installStatus.installed) {
    return { ok: true, skipped: true };
  }

  const model = storeData.nous?.model || DEFAULT_NOUS_MODEL;
  const configSets = [
    ['model.provider', 'custom'],
    ['model.default', model],
    ['model.base_url', NOUS_INFERENCE_BASE],
    ['model.api_key', '${NOUS_API_KEY}'],
  ];

  try {
    for (const [key, value] of configSets) {
      execFileSync(installStatus.path, ['config', 'set', key, value, '--force'], {
        cwd: HERMES_INSTALL,
        env: hermesCliEnv(),
        timeout: 20000,
        windowsHide: true,
      });
    }
    appendLog('✅ Hermes config synced for Nous Portal API key', 'success');
    return { ok: true };
  } catch (e) {
    appendLog(`⚠ Hermes config sync: ${e.message}`, 'warn');
    return { ok: false, error: e.message };
  }
}

async function syncHermesCredentials(token, { restartGateway = false } = {}) {
  const nousKey = resolveNousApiKey();
  if (!nousKey) {
    return {
      ok: false,
      msg: 'Nous Portal API key not set — open Setup tab, enter your key, and Save.',
    };
  }
  if (!String(storeData.nous?.apiKey || '').trim()) {
    storeData.nous = { ...(storeData.nous || {}), apiKey: nousKey };
  }

  fs.mkdirSync(HERMES_HOME, { recursive: true });
  const envPath = getHermesEnvPath();
  const before = fs.existsSync(envPath) ? fs.readFileSync(envPath, 'utf8') : '';
  let after = upsertEnvVar(before, 'NOUS_API_KEY', nousKey);
  after = upsertEnvVar(after, 'NOUSRESEARCH_API_KEY', nousKey);
  if (after !== before) {
    fs.writeFileSync(envPath, after, 'utf8');
    appendLog('✅ Synced Nous API key to Hermes .env', 'success');
  }

  syncHermesConfig();

  if (token) {
    for (const keyName of ['NOUS_API_KEY', 'NOUSRESEARCH_API_KEY']) {
      try {
        const res = await hermesApiRequest('PUT', '/api/env', { key: keyName, value: nousKey }, token);
        if (res.status >= 200 && res.status < 300) {
          appendLog(`✅ ${keyName} registered with Hermes`, 'success');
        } else {
          appendLog(`⚠ Hermes env API (${keyName}) returned ${res.status}`, 'warn');
        }
      } catch (e) {
        appendLog(`⚠ Hermes env API sync (${keyName}): ${e.message}`, 'warn');
      }
    }
  }

  if (restartGateway && token) {
    try {
      appendLog('↻ Restarting gateway so cron picks up Nous credentials…', 'info');
      await hermesApiRequest('POST', '/api/gateway/stop?profile=default', null, token);
      await new Promise((resolve) => setTimeout(resolve, 1500));
      const cli = await startGatewayViaCli();
      if (!cli.ok) {
        await hermesApiRequest('POST', '/api/gateway/start?profile=default', null, token);
      }
      const deadline = Date.now() + 30000;
      while (Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        try {
          const status = await fetchHermesStatus();
          if (status.gateway_running) break;
        } catch {}
      }
    } catch (e) {
      appendLog(`⚠ Gateway restart: ${e.message}`, 'warn');
    }
  }

  return { ok: true };
}

function writeCompendiumFile() {
  const p = getCompendiumPath();
  const isDemo = !!storeData.blofin?.demoMode;
  fs.writeFileSync(p, [
    '# My Blofin API Compendium',
    `# Mode: ${isDemo ? 'DEMO / SIMULATED TRADING' : 'LIVE TRADING'}`,
    `# Base URL: ${isDemo ? BLOFIN_DEMO_URL : BLOFIN_LIVE_URL}`,
    '# Generated by KnightTrader — do not share this file',
    '',
    `Passphrase: ${storeData.blofin.passphrase}`,
    `API Key: ${storeData.blofin.apiKey}`,
    `API Secret: ${storeData.blofin.secretKey}`,
    '',
    '# AI Credentials (Nous Portal)',
    `NOUS_API_KEY: ${storeData.nous.apiKey}`,
    `NOUS_MODEL: ${storeData.nous.model || DEFAULT_NOUS_MODEL}`,
    '',
    `# Generated: ${new Date().toISOString()}`
  ].join('\n'), 'utf8');
  try {
    syncHermesCredentials(null).catch((e) => {
      appendLog(`⚠ Hermes .env sync: ${e.message}`, 'warn');
    });
  } catch (e) {
    appendLog(`⚠ Hermes .env sync: ${e.message}`, 'warn');
  }
  return p;
}

// ── Credential file parsing / picker ───────────────────────────────────────
function normalizeCredentialKey(key) {
  return String(key || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function coerceBool(value) {
  if (typeof value === 'boolean') return value;
  const v = String(value || '').trim().toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(v)) return true;
  if (['0', 'false', 'no', 'off'].includes(v)) return false;
  return null;
}

function stripCredentialValue(value) {
  let v = String(value ?? '').trim();
  if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
    v = v.slice(1, -1).trim();
  }
  return v;
}

function looksLikeApiKey(value) {
  const v = String(value || '').trim();
  if (v.length < 8) return false;
  if (/^sk[-_a-z0-9.]+$/i.test(v)) return true;
  if (/^[a-z0-9._-]{16,}$/i.test(v)) return true;
  return false;
}

function applyCredentialMapping(target, kv) {
  const set = (section, field, value) => {
    if (value == null || value === '') return;
    target[section][field] = value;
  };

  for (const [rawKey, rawValue] of Object.entries(kv)) {
    const key = normalizeCredentialKey(rawKey);
    const value = stripCredentialValue(rawValue);
    if (!value) continue;

    if (key === 'nous_api_key' || key === 'nouse_api_key' || key === 'portal_api_key' || key === 'nous_portal_api_key') {
      set('nous', 'apiKey', value);
    } else if (key === 'nous_model' || key === 'nouse_model') {
      set('nous', 'model', normalizeNousModel(value));
    } else if (key === 'api_key' || key === 'blofin_api_key') set('blofin', 'apiKey', value);
    else if (key === 'api_secret' || key === 'secret_key' || key === 'blofin_secret_key') set('blofin', 'secretKey', value);
    else if (key === 'passphrase' || key === 'blofin_passphrase') set('blofin', 'passphrase', value);
    else if (key === 'blofin_demo_mode' || key === 'demo_mode') {
      const demo = coerceBool(value);
      if (demo !== null) target.blofin.demoMode = demo;
    }
  }
}

function finalizeNousCredentials(parsed, text) {
  if (parsed.nous.apiKey) return;

  const hasBlofin = !!(parsed.blofin.apiKey || parsed.blofin.secretKey || parsed.blofin.passphrase);
  if (!hasBlofin && parsed.blofin.apiKey) {
    parsed.nous.apiKey = parsed.blofin.apiKey;
    parsed.blofin.apiKey = '';
  }

  const lines = String(text || '')
    .replace(/^\uFEFF/, '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'));

  for (const line of lines) {
    const labeled = line.match(/^(?:nous\s*)?(?:portal\s*)?api\s*key[^:=]*[:=]\s*(.+)$/i);
    if (labeled) {
      parsed.nous.apiKey = stripCredentialValue(labeled[1]);
      return;
    }
  }

  const rawLines = lines.filter((line) => !/[:=]/.test(line));
  if (rawLines.length === 1 && looksLikeApiKey(rawLines[0])) {
    parsed.nous.apiKey = rawLines[0];
    return;
  }

  if (lines.length === 1) {
    const parts = lines[0].split(/[:=]/);
    if (parts.length >= 2) {
      const candidate = stripCredentialValue(parts.slice(1).join('='));
      if (looksLikeApiKey(candidate)) parsed.nous.apiKey = candidate;
    } else if (looksLikeApiKey(lines[0])) {
      parsed.nous.apiKey = lines[0];
    }
  }
}

function mergeCredentialObjects(target, source) {
  if (!source || typeof source !== 'object') return;
  if (source.nous && typeof source.nous === 'object') {
    if (source.nous.apiKey) target.nous.apiKey = String(source.nous.apiKey).trim();
    if (source.nous.model) target.nous.model = normalizeNousModel(source.nous.model);
  }
  if (source.nouse && typeof source.nouse === 'object') {
    if (source.nouse.apiKey) target.nous.apiKey = String(source.nouse.apiKey).trim();
    if (source.nouse.model) target.nous.model = normalizeNousModel(source.nouse.model);
  }
  if (source.blofin && typeof source.blofin === 'object') {
    if (source.blofin.apiKey) target.blofin.apiKey = String(source.blofin.apiKey).trim();
    if (source.blofin.secretKey) target.blofin.secretKey = String(source.blofin.secretKey).trim();
    if (source.blofin.passphrase) target.blofin.passphrase = String(source.blofin.passphrase).trim();
    if (source.blofin.demoMode != null) {
      const demo = coerceBool(source.blofin.demoMode);
      if (demo !== null) target.blofin.demoMode = demo;
    }
  }
}

function parseCredentialFileContent(content) {
  const parsed = {
    nous: { apiKey: '', model: '' },
    blofin: { apiKey: '', secretKey: '', passphrase: '', demoMode: null },
  };
  const text = String(content || '').trim();
  if (!text) return parsed;

  if (text.startsWith('{') || text.startsWith('[')) {
    try {
      mergeCredentialObjects(parsed, JSON.parse(text));
      if (parsed.nous.apiKey || parsed.nous.model || parsed.blofin.apiKey) return parsed;
    } catch {}
  }

  const kv = {};
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (trimmed.startsWith('#')) {
      if (/demo/i.test(trimmed) && /(mode|simulated|trading)/i.test(trimmed)) parsed.blofin.demoMode = true;
      if (trimmed.includes('demo-trading-openapi.blofin.com')) parsed.blofin.demoMode = true;
      if (/live/i.test(trimmed) && /(mode|trading)/i.test(trimmed) && !/demo/i.test(trimmed)) parsed.blofin.demoMode = false;
      continue;
    }
    const match = trimmed.match(/^([^:=#]+?)[:=]\s*(.+)$/);
    if (match) kv[normalizeCredentialKey(match[1])] = match[2].trim();
  }
  applyCredentialMapping(parsed, kv);
  finalizeNousCredentials(parsed, text);
  return parsed;
}

function getNousCredentialDefaultPath() {
  const candidates = [
    path.join(os.homedir(), 'OneDrive', 'Documents'),
    path.join(os.homedir(), 'Documents'),
    path.join(os.homedir(), 'Downloads'),
  ];
  return candidates.find((p) => fs.existsSync(p)) || candidates[0];
}

async function pickCredentialFile(kind) {
  const defaultPath = kind === 'blofin'
    ? getCompendiumPath()
    : getNousCredentialDefaultPath();

  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
    title: kind === 'blofin' ? 'Select Blofin credentials file' : 'Select Nous Portal credentials file',
    defaultPath: fs.existsSync(defaultPath) ? defaultPath : path.dirname(defaultPath),
    properties: ['openFile'],
    filters: [
      { name: 'Credential files', extensions: ['txt', 'env', 'json', 'yaml', 'yml', 'md'] },
      { name: 'All files', extensions: ['*'] },
    ],
  });

  if (canceled || !filePaths?.[0]) return { ok: false, cancelled: true };

  const filePath = filePaths[0];
  try {
    const parsed = parseCredentialFileContent(fs.readFileSync(filePath, 'utf8'));

    if (kind === 'nous') {
      const nous = {
        apiKey: parsed.nous.apiKey || '',
        model: normalizeNousModel(parsed.nous.model),
      };
      if (!nous.apiKey) {
        return { ok: false, error: 'No Nous Portal API key found in that file.', path: filePath };
      }
      appendLog(`📂 Loaded Nous credentials from ${filePath}`, 'success');
      return { ok: true, path: filePath, nous };
    }

    const blofin = {
      apiKey: parsed.blofin.apiKey || '',
      secretKey: parsed.blofin.secretKey || '',
      passphrase: parsed.blofin.passphrase || '',
    };
    if (parsed.blofin.demoMode !== null) blofin.demoMode = parsed.blofin.demoMode;

    if (!blofin.apiKey && !blofin.secretKey && !blofin.passphrase) {
      return { ok: false, error: 'No Blofin credentials found in that file.', path: filePath };
    }
    appendLog(`📂 Loaded Blofin credentials from ${filePath}`, 'success');
    return { ok: true, path: filePath, blofin };
  } catch (e) {
    return { ok: false, error: e.message, path: filePath };
  }
}

// ── State ──────────────────────────────────────────────────────────────────
let hermesDashProcess = null;
let dashboardReady    = false;
let dashboardSessionToken = null;
let dashboardLastOutput = [];
let mainWindow        = null;
let logBuffer         = [];
let appTray           = null;
let trayReady         = false;

function appendLog(msg, type = 'info') {
  const entry = { ts: new Date().toISOString(), type, msg: String(msg) };
  logBuffer.push(entry);
  if (logBuffer.length > 500) logBuffer.shift();
  try {
    if (mainWindow && !mainWindow.isDestroyed() && mainWindow.webContents && !mainWindow.webContents.isDestroyed()) {
      mainWindow.webContents.send('log-line', entry);
    }
  } catch {} // window or webContents may be mid-destroy — swallow silently
}

function buildTray() {
  if (trayReady || appTray) return;
  try {
    const iconPath = path.join(__dirname, 'assets', 'tray-icon.png');
    const icon = nativeImage.createFromPath(iconPath);
    const image = icon.isEmpty() ? nativeImage.createEmpty() : icon;
    trayReady = true;
    appTray = new Tray(image);
    appTray.setToolTip('KnightTrader Blofin');
    const contextMenu = Menu.buildFromTemplate([
      { label: 'Show KnightTrader', click: () => restoreFromTray() },
      { label: 'Quit', click: () => quitFromTray() },
    ]);
    appTray.setContextMenu(contextMenu);
    appTray.on('double-click', restoreFromTray);
    appendLog('🧩 System tray ready — close button now minimizes to tray', 'info');
  } catch (e) {
    appendLog(`⚠ Tray init failed: ${e.message}`, 'warn');
  }
}

function restoreFromTray() {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    if (mainWindow.isVisible()) mainWindow.focus();
    else mainWindow.show();
  }
}

function quitFromTray() {
  trayReady = false;
  if (appTray) {
    try { appTray.destroy(); } catch {}
    appTray = null;
  }
  stopHermesDashboard();
  if (mainWindow) {
    try { mainWindow.destroy(); } catch {}
  }
  app.quit();
}

// ── Hermes install status ──────────────────────────────────────────────────
function psSingleQuote(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

function normalizeProcessExitCode(code) {
  if (code == null) return -1;
  return code > 2147483647 ? code - 4294967296 : code;
}

function findHermesExecutable() {
  const candidates = [
    path.join(HERMES_INSTALL, 'venv', 'Scripts', 'hermes.exe'),
    path.join(HERMES_INSTALL, 'venv', 'Scripts', 'hermes'),
    path.join(HERMES_INSTALL, 'bin', 'hermes.exe'),
    path.join(HERMES_INSTALL, 'bin', 'hermes'),
    path.join(HERMES_INSTALL, '.venv', 'Scripts', 'hermes.exe'),
    path.join(HERMES_INSTALL, '.venv', 'Scripts', 'hermes'),
    path.join(HERMES_INSTALL, '.venv', 'bin', 'hermes'),
    HERMES_EXE,
    path.join(HERMES_HOME, 'bin', 'hermes.exe'),
    path.join(HERMES_HOME, 'bin', 'hermes'),
  ];
  return candidates.find((p) => fs.existsSync(p)) || null;
}

function writeHermesInstallLauncher() {
  const launcherPath = path.join(os.tmpdir(), `knighttrader-hermes-launcher-${process.pid}.ps1`);
  const script = [
    "$ErrorActionPreference = 'Stop'",
    `$HermesHome = ${psSingleQuote(HERMES_HOME)}`,
    `$InstallDir = ${psSingleQuote(HERMES_INSTALL)}`,
    '$env:HERMES_HOME = $HermesHome',
    '',
    "$installerUrl = 'https://hermes-agent.nousresearch.com/install.ps1'",
    "$installerPath = Join-Path $env:TEMP 'knighttrader-hermes-install.ps1'",
    '',
    "Write-Host 'Downloading Hermes installer...'",
    'try {',
    '  (Invoke-RestMethod -Uri $installerUrl -UseBasicParsing) | Set-Content -Path $installerPath -Encoding UTF8',
    '} catch {',
    '  Write-Error ("Failed to download installer: " + $_.Exception.Message)',
    '  exit 1',
    '}',
    '',
    "Write-Host 'Running Hermes installer into sandbox...'",
    '& $installerPath -HermesHome $HermesHome -InstallDir $InstallDir -NonInteractive',
    'if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) { exit $LASTEXITCODE }',
    'exit 0',
  ].join('\r\n');
  fs.writeFileSync(launcherPath, script, 'utf8');
  return launcherPath;
}

function checkHermesInstalled() {
  const exe = findHermesExecutable();
  if (exe) {
    try {
      const v = execFileSync(exe, ['--version'], { timeout: 5000 }).toString().trim();
      return { installed: true, version: v, path: exe };
    } catch {
      return { installed: true, version: 'unknown', path: exe };
    }
  }
  if (fs.existsSync(HERMES_INSTALL)) {
    return { installed: false, partial: true, path: HERMES_INSTALL };
  }
  return { installed: false, partial: false };
}

// ── Sandboxed install ──────────────────────────────────────────────────────
// Downloads install.ps1, then invokes it with -HermesHome/-InstallDir.
// Uses a temp launcher script (not inline iex) so paths with spaces/apostrophes work.
function installHermes() {
  return new Promise((resolve) => {
    appendLog('📦 Installing Hermes into sandboxed location:', 'info');
    appendLog(`   HERMES_HOME  = ${HERMES_HOME}`, 'info');
    appendLog(`   InstallDir   = ${HERMES_INSTALL}`, 'info');

    fs.mkdirSync(HERMES_HOME, { recursive: true });

    let launcherPath;
    try {
      launcherPath = writeHermesInstallLauncher();
    } catch (e) {
      appendLog(`❌ Failed to prepare installer: ${e.message}`, 'error');
      resolve({ ok: false, error: e.message });
      return;
    }

    const proc = spawn('powershell.exe', [
      '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', launcherPath
    ], {
      windowsHide: true,
      env: {
        ...process.env,
        HERMES_HOME: HERMES_HOME,
      },
    });

    proc.stdout.on('data', (d) => {
      d.toString().split('\n').filter(Boolean).forEach((line) => {
        if (/restart your terminal/i.test(line)) {
          appendLog(`${line} (safe to ignore in KnightTrader — no terminal restart needed)`, 'info');
          return;
        }
        appendLog(line, 'info');
      });
    });
    proc.stderr.on('data', (d) => d.toString().split('\n').filter(Boolean).forEach((l) => appendLog(l, 'warn')));

    proc.on('close', async (code) => {
      try { fs.unlinkSync(launcherPath); } catch {}

      const status = checkHermesInstalled();
      if (status.installed) {
        appendLog(`✅ Hermes installed: ${status.version}`, 'success');
        ensureHermesExecutableRunnable(status.path);
        appendLog('🔒 Hermes is sandboxed to this app folder (AppData\\knight-trader\\hermes).', 'info');
        try {
          await syncHermesCredentials(null);
        } catch (e) {
          appendLog(`⚠ Post-install credential sync: ${e.message}`, 'warn');
        }
        appendLog('▶ Starting dashboard + gateway now so Step 3 works on first click…', 'info');
        try {
          const started = await startHermesDashboard();
          if (started.ok) appendLog('✅ Dashboard + gateway ready after install', 'success');
          else appendLog(`⚠ Dashboard not ready yet: ${started.msg || started.error}. Click Start Dashboard.`, 'warn');
        } catch (e) {
          appendLog(`⚠ Dashboard start after install: ${e.message}`, 'warn');
        }
        resolve({ ok: true, version: status.version, path: status.path, isolated: true });
        return;
      }

      const exitCode = normalizeProcessExitCode(code);
      if (status.partial) {
        appendLog('⚠ Install incomplete — click Install again to resume.', 'warn');
        resolve({ ok: false, partial: true, code: exitCode, path: status.path });
        return;
      }

      appendLog(`❌ Install script failed (exit ${exitCode})`, 'error');
      resolve({ ok: false, code: exitCode });
    });

    proc.on('error', (e) => {
      try { fs.unlinkSync(launcherPath); } catch {}
      appendLog(`❌ Failed to launch installer: ${e.message}`, 'error');
      resolve({ ok: false, error: e.message });
    });
  });
}

// Low integrity on hermes.exe prevents npm/uvicorn from writing the web UI
// and makes dashboard start fail for customers. Keep Hermes in AppData only.
function ensureHermesExecutableRunnable(exePath) {
  if (!exePath || !fs.existsSync(exePath)) return;
  try {
    execFileSync('icacls', [exePath, '/setintegritylevel', 'Medium'], {
      timeout: 8000,
      windowsHide: true,
    });
  } catch (e) {
    appendLog(`⚠ Could not reset Hermes integrity level: ${e.message}`, 'warn');
  }
}

// ── Start sandboxed Hermes dashboard ──────────────────────────────────────
function probeDashboardPort(port, timeoutMs = 1500) {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/api/health`, (res) => {
      res.resume();
      resolve(true);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(timeoutMs, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function findAvailableDashboardPort() {
  for (const port of DASHBOARD_PORT_CANDIDATES) {
    if (await probeDashboardPort(port, DASHBOARD_PORT_PROBE_TIMEOUT)) {
      return port;
    }
  }
  return null;
}

function hermesWebDistReady() {
  return fs.existsSync(path.join(HERMES_INSTALL, 'hermes_cli', 'web_dist', 'index.html'));
}

function dashboardSpawnArgs() {
  const args = ['dashboard', '--no-open', '--host', '127.0.0.1', '--port', String(DASHBOARD_PORT)];
  if (hermesWebDistReady()) args.push('--skip-build');
  return args;
}

function ensureDashboardSessionToken() {
  if (!dashboardSessionToken) {
    dashboardSessionToken = crypto.randomBytes(24).toString('base64url');
  }
  return dashboardSessionToken;
}

function scrapeDashboardSessionToken(html) {
  const match = String(html || '').match(/__HERMES_SESSION_TOKEN__\s*=\s*"([^"]+)"/);
  return match ? match[1] : null;
}

function fetchDashboardSessionToken(forceRefresh = false) {
  if (dashboardSessionToken && !forceRefresh) return Promise.resolve(dashboardSessionToken);
  return new Promise((resolve, reject) => {
    const req = http.get(DASHBOARD_URL, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        const token = scrapeDashboardSessionToken(data);
        if (token) {
          dashboardSessionToken = token;
          resolve(dashboardSessionToken);
          return;
        }
        if (dashboardSessionToken) {
          resolve(dashboardSessionToken);
          return;
        }
        reject(new Error('Could not read dashboard session token'));
      });
    });
    req.on('error', reject);
    req.setTimeout(8000, () => {
      req.destroy();
      reject(new Error('Dashboard token request timed out'));
    });
  });
}

function hermesApiRequest(method, apiPath, body, token) {
  return new Promise((resolve, reject) => {
    const port = activeDashboardPort || DASHBOARD_PORT;
    const payload = body == null ? null : JSON.stringify(body);
    const req = http.request({
      hostname: '127.0.0.1',
      port,
      path: apiPath,
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-Hermes-Session-Token': token,
        Authorization: `Bearer ${token}`,
        ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}),
      },
    }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        let parsed = data;
        try { parsed = JSON.parse(data); } catch {}
        resolve({ status: res.statusCode || 0, body: parsed });
      });
    });
    req.on('error', reject);
    req.setTimeout(20000, () => {
      req.destroy();
      reject(new Error('Hermes API request timed out'));
    });
    if (payload) req.write(payload);
    req.end();
  });
}

function dashboardSpawnEnv() {
  const token = ensureDashboardSessionToken();
  const env = hermesChildEnv({
    HERMES_DASHBOARD_SESSION_TOKEN: token,
    NOUS_MODEL: storeData.nous?.model || DEFAULT_NOUS_MODEL,
  });
  const blofinKey = String(storeData.blofin?.apiKey || '').trim();
  const blofinSecret = String(storeData.blofin?.secretKey || '').trim();
  const blofinPass = String(storeData.blofin?.passphrase || '').trim();
  if (blofinKey) env.BLOFIN_API_KEY = blofinKey;
  if (blofinSecret) env.BLOFIN_SECRET_KEY = blofinSecret;
  if (blofinPass) env.BLOFIN_PASSPHRASE = blofinPass;
  return env;
}

function fetchHermesStatus() {
  return new Promise((resolve, reject) => {
    const req = http.get(`${DASHBOARD_URL}/api/status`, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          reject(new Error('Invalid Hermes status response'));
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(8000, () => {
      req.destroy();
      reject(new Error('Hermes status request timed out'));
    });
  });
}

async function waitForDashboardPort(maxMs = 480000) {
  const start = Date.now();
  let lastBeat = 0;
  while (Date.now() - start < maxMs) {
    if (await probeDashboardPort()) return true;
    if (!isDashboardProcessAlive() && Date.now() - start > 4000) {
      const tail = dashboardLastOutput.slice(-8).join(' | ');
      appendLog(`⚠ Dashboard process exited before it was ready${tail ? `: ${tail}` : ''}`, 'error');
      return false;
    }
    if (Date.now() - lastBeat > 15000) {
      const secs = Math.round((Date.now() - start) / 1000);
      appendLog(`⏳ Waiting for Hermes dashboard (${secs}s) — first start builds the web UI`, 'info');
      lastBeat = Date.now();
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return false;
}

async function startGatewayViaCli() {
  const installStatus = checkHermesInstalled();
  if (!installStatus.installed) return { ok: false, msg: 'Hermes not installed' };
  return new Promise((resolve) => {
    appendLog('▶ Starting Hermes gateway via CLI…', 'info');
    let settled = false;
    const proc = spawn(installStatus.path, ['-p', 'default', 'gateway', 'start'], {
      cwd: HERMES_INSTALL,
      windowsHide: true,
      env: dashboardSpawnEnv(),
      detached: true,
      stdio: 'ignore',
    });
    proc.on('error', (e) => {
      if (!settled) {
        settled = true;
        resolve({ ok: false, msg: e.message });
      }
    });
    proc.once('spawn', () => {
      if (!settled) {
        settled = true;
        proc.unref();
        resolve({ ok: true });
      }
    });
  });
}

async function ensureGatewayRunning(token) {
  let status;
  try {
    status = await fetchHermesStatus();
    if (status.gateway_running) {
      appendLog('✅ Hermes gateway already running', 'success');
      return { ok: true, status };
    }
    } catch (e) {
    appendLog(`⚠ Could not read Hermes status: ${e.message}`, 'warn');
  }

  appendLog('▶ Starting Hermes gateway (required for cron jobs)…', 'info');
  let startRes;
  try {
    startRes = await hermesApiRequest('POST', '/api/gateway/start?profile=default', null, token);
    if (startRes.status === 401) {
      const fresh = await fetchDashboardSessionToken(true);
      startRes = await hermesApiRequest('POST', '/api/gateway/start?profile=default', null, fresh);
    }
    if (startRes.status >= 300) {
      appendLog(`⚠ Gateway API start returned ${startRes.status} — trying CLI`, 'warn');
      const cli = await startGatewayViaCli();
      if (!cli.ok) {
        const detail = typeof startRes.body === 'object'
          ? (startRes.body.detail || JSON.stringify(startRes.body))
          : String(startRes.body);
        return { ok: false, msg: `Gateway start failed: ${detail}` };
      }
    }
  } catch (e) {
    appendLog(`⚠ Gateway API start: ${e.message} — trying CLI`, 'warn');
    const cli = await startGatewayViaCli();
    if (!cli.ok) return { ok: false, msg: `Gateway start failed: ${e.message}` };
  }

  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    try {
      status = await fetchHermesStatus();
      if (status.gateway_running) {
        appendLog(`✅ Hermes gateway running (state: ${status.gateway_state || 'running'})`, 'success');
        return { ok: true, status };
      }
    } catch {}
  }

  return { ok: false, msg: 'Gateway did not become ready in 90s — check Logs tab' };
}

async function ensureDashboardAndGateway() {
  const portReady = await waitForDashboardPort();
  if (!portReady) {
    const tail = dashboardLastOutput.slice(-6).join(' | ');
    return {
      ok: false,
      msg: tail
        ? `Dashboard did not respond on port 9119. ${tail}`
        : 'Dashboard did not respond on port 9119',
    };
  }

  let token;
  try {
    token = await fetchDashboardSessionToken();
  } catch (e) {
    return { ok: false, msg: e.message };
  }

  let gatewayWasRunning = false;
  try {
    const statusBefore = await fetchHermesStatus();
    gatewayWasRunning = !!statusBefore.gateway_running;
  } catch {}

  const sync = await syncHermesCredentials(token, { restartGateway: gatewayWasRunning });
  if (!sync.ok) {
    appendLog(`⚠ ${sync.msg || sync.error || 'Credential sync skipped'} — starting gateway anyway`, 'warn');
  }

  const gateway = await ensureGatewayRunning(token);
  if (!gateway.ok) return gateway;

  signalDashboardReady(gateway.status);
  return { ok: true, attached: !hermesDashProcess, gatewayRunning: true };
}

async function getDashboardStatus() {
  const portUp = await probeDashboardPort();
  let gatewayRunning = false;
  if (portUp) {
    try {
      const status = await fetchHermesStatus();
      gatewayRunning = !!status.gateway_running;
      dashboardReady = gatewayRunning;
    } catch {
  dashboardReady = false;
    }
  } else {
    dashboardReady = false;
  }
  return {
    running: !!hermesDashProcess || portUp,
    ready: dashboardReady,
    gatewayRunning,
    url: DASHBOARD_URL,
  };
}

function isDashboardProcessAlive() {
  return !!(hermesDashProcess && hermesDashProcess.exitCode == null && !hermesDashProcess.killed);
}

function rememberDashboardOutput(chunk, type) {
  String(chunk).split(/\r?\n/).filter(Boolean).forEach((line) => {
    dashboardLastOutput.push(line);
    if (dashboardLastOutput.length > 40) dashboardLastOutput.shift();
    appendLog(line, type);
  });
}

async function startHermesDashboard() {
  const installStatus = checkHermesInstalled();
  if (!installStatus.installed) {
    return { ok: false, msg: 'Hermes not installed yet. Run Step 1 first.' };
  }

  ensureHermesExecutableRunnable(installStatus.path);
  dashboardReady = false;

  if (await probeDashboardPort()) {
    appendLog('ℹ Dashboard already listening — ensuring gateway is running…', 'info');
    return ensureDashboardAndGateway();
  }

  if (!isDashboardProcessAlive()) {
    dashboardLastOutput = [];
    appendLog('▶ Starting Hermes dashboard + gateway on port 9119…', 'info');
    appendLog(`  Using: ${installStatus.path}`, 'info');
    if (!hermesWebDistReady()) {
      appendLog('  First start builds the Hermes web UI (can take a few minutes)…', 'info');
    }

    const preSync = await syncHermesCredentials(null);
    if (!preSync.ok) {
      appendLog(`⚠ ${preSync.msg || preSync.error || 'Credential sync skipped'} — starting dashboard anyway`, 'warn');
    }

    hermesDashProcess = spawn(installStatus.path, dashboardSpawnArgs(), {
      cwd: HERMES_INSTALL,
      windowsHide: true,
      env: dashboardSpawnEnv(),
    });

    hermesDashProcess.stdout.on('data', (d) => rememberDashboardOutput(d, 'info'));
    hermesDashProcess.stderr.on('data', (d) => rememberDashboardOutput(d, 'warn'));
    hermesDashProcess.on('error', (e) => appendLog(`Dashboard error: ${e.message}`, 'error'));
    hermesDashProcess.on('close', async (code) => {
    hermesDashProcess = null;
      if (await probeDashboardPort()) return;
    dashboardReady = false;
      appendLog(`◼ Hermes dashboard stopped (code ${normalizeProcessExitCode(code)})`, code === 0 ? 'info' : 'error');
    mainWindow?.webContents?.send('dashboard-stopped', {});
  });
  } else {
    appendLog('ℹ Hermes dashboard is still starting — waiting for port 9119…', 'info');
  }

  return ensureDashboardAndGateway();
}

function signalDashboardReady(status) {
  if (dashboardReady) return;
  dashboardReady = true;
  const gatewayNote = status?.gateway_running ? ' — gateway running, cron can fire' : '';
  appendLog(`✅ Hermes ready at ${DASHBOARD_URL}${gatewayNote}`, 'success');
  mainWindow?.webContents?.send('dashboard-ready', {
    url: DASHBOARD_URL,
    gatewayRunning: !!status?.gateway_running,
  });
}

async function stopHermesDashboard() {
  if (await probeDashboardPort()) {
    try {
      const token = await fetchDashboardSessionToken();
      appendLog('⏹ Stopping Hermes gateway…', 'info');
      await hermesApiRequest('POST', '/api/gateway/stop?profile=default', null, token);
    } catch (e) {
      appendLog(`⚠ Gateway stop: ${e.message}`, 'warn');
    }
  }

  if (hermesDashProcess) {
    hermesDashProcess.kill();
  hermesDashProcess = null;
  } else if (await probeDashboardPort()) {
    const status = checkHermesInstalled();
    if (status.installed) {
      try {
        execFileSync(status.path, ['dashboard', '--stop'], {
          timeout: 20000,
          cwd: HERMES_INSTALL,
          env: dashboardSpawnEnv(),
        });
      } catch (e) {
        appendLog(`⚠ Dashboard stop: ${e.message}`, 'warn');
      }
    }
  }

  dashboardReady = false;
  dashboardSessionToken = null;
  appendLog('⏹ Hermes dashboard stopped.', 'warn');
  mainWindow?.webContents?.send('dashboard-stopped', {});
  return { ok: true };
}

// ── Cron configuration ─────────────────────────────────────────────────────
function buildCronPrompt() {
  const compPath = getCompendiumPath();
  const isDemo = !!storeData.blofin?.demoMode;
  const targetUrl = isDemo ? BLOFIN_DEMO_URL : BLOFIN_LIVE_URL;
  const targetMode = isDemo ? 'DEMO / SIMULATED (Testing with Virtual Funds)' : 'LIVE TRADING';

  return `LEARNING ACROSS CRON TICKS (READ FIRST)
Each cron run is a fresh session. Do not assume chat memory from prior ticks.
Before trading: read your durable learning artifacts (skills / memory / lessons files under ${HERMES_HOME} and any project lessons files) and apply them.
If lessons say a setup type loses, respect that. If lessons say a setup type wins, bias toward it only when live structure still confirms.
Learning that stays only in this turn's reply is wasted — you must use durable files.

VPN IS IN BLOFIN ACCEPTED COUNTRY. USE CAMOUFOX TO TRADE. TROUBLESHOOT AND FIX ANY/ALL ISSUES THAT ARISE.

MISSION
Scan and manually trade the Blofin account in ${targetMode} mode.
Target Base URL: ${targetUrl}
You are the trading automation. Take all trades by hand. Zero trading scripts, agents, assistants, and bots are to be used — zero. No order-placing bots, no auto-scanners that submit orders, no "run agent" wrappers that trade for you. You decide, you place, you manage TP/SL, you monitor.

CREDENTIALS
Use exactly: ${compPath}
(Passphrase / API Key / API Secret). Prefer this file over any older repo credentials/blofin.txt paths. Confirm which key is loaded before first private call.

SCOREBOARD
Only scoreboard: take and keep the Blofin equity curve vertical. No rushing. No forced entries. Isolated margin only. Longs and shorts both allowed when the edge is real. Do not deny a good edge just because other positions are open. Never be in a rush to lose money. Sizing: size conservatively, protect equity, take real edges when they appear.

--- HOW TO ACTUALLY GET TRADES THROUGH ---
What looks like a hard block is usually NOT "Blofin banned you" and NOT "API keys invalid."

SYMPTOM
Private REST calls return HTML instead of JSON. Signed clients report: Failed to get server time, empty account, placeOrder never reached. That is a transport / WAF / fingerprint problem, not a strategy problem.

WHY IT HAPPENS
1) Plain Python requests / default User-Agent hits Cloudflare or Blofin edge WAF and gets HTML.
2) Base URL: ${targetUrl} (${targetMode}).
3) Wrong or stale credentials file loaded.
4) Broken/incompatible PyPI blofin package. Do not depend on it as the only path.
5) Clock skew on signed requests — sync to Blofin server time when signing.
6) Missing ACCESS headers / passphrase / brokerId when the key requires them.
7) USDT still sitting in Funding instead of Futures / USDT-M — transfer first.

REQUIRED FIX ORDER
A) Verify VPN exit IP is still in an accepted country.
B) Prefer Camoufox (browser) for any UI confirmation AND for establishing a real browser TLS/JA3 fingerprint. Use Camoufox to open Blofin, confirm account/login/state if API is cloudy, and to manually place/verify orders when REST is fighting WAF.
C) For API: use curl_cffi (or equivalent) with Chrome impersonation. Set Origin/Referer to blofin.com. Retry impersonation profiles on 403 HTML.
D) Confirm live endpoints and live credentials. Test in this order: public time → public tickers → signed balance → positions → one tiny isolated order with TP/SL only after balance reads as JSON.
E) If "Failed to get server time": fix transport first (CF bypass), then re-sync timestamp.
F) If package SDK is broken: call REST directly with correct ACCESS-KEY / ACCESS-SIGN / ACCESS-TIMESTAMP / ACCESS-PASSPHRASE. Parse only JSON.
G) Never fall back to a fake demo balance when live sync fails. Fix the pipe, then trade.
H) Confirm Futures / USDT-M available balance is non-zero before claiming there is nothing to trade.

SUCCESS CRITERIA FOR "API WORKS"
- Account balance returns JSON with real USDT equity/available.
- Positions/orders endpoints return JSON.
- A manual order you place shows up on Blofin.

--- TRADING RULES (MANUAL, AUTONOMOUS) ---
Scan the full USDT universe yourself. Manually choose entries. Place orders yourself. Attach TP/SL yourself. Isolated margin only. Prefer clarity over activity. Compound wins; do not force rotations with thin free margin. Stay open to longs and shorts. With a small account, prefer the smallest valid size that still has a clear edge.

PROCEED NOW
Confirm credentials path → confirm VPN accepted country → prove JSON account read (Camoufox and/or curl_cffi) → confirm Futures USDT → scan → take righteous trades by hand → manage positions → keep equity curve vertical.

LEARNING ACROSS CRON TICKS (WRITE BEFORE YOU FINISH)
After this cycle: write what worked, what failed, and the exact reusable rule into a durable skill or lessons file under ${HERMES_HOME}.
Include: symbol/setup type, long or short, why taken or skipped, outcome if known, and the next-tick rule.
Next tick must be able to load and use those updated lessons with no chat history.
If nothing material changed, still append a one-line "hold / no edge" note with timestamp.`;
}

async function configureCron() {
  if (!(await probeDashboardPort())) {
    appendLog('⚠ Start the Hermes dashboard before configuring cron', 'warn');
    return { ok: false, msg: 'Start the Hermes dashboard first.', prompt: buildCronPrompt() };
  }

  let token;
  try {
    token = await fetchDashboardSessionToken();
  } catch (e) {
    appendLog(`⚠ Dashboard auth failed: ${e.message}`, 'warn');
    return { ok: false, msg: e.message, prompt: buildCronPrompt() };
  }

  const sync = await syncHermesCredentials(token, { restartGateway: true });
  if (!sync.ok) {
    return { ok: false, msg: sync.msg, prompt: buildCronPrompt() };
  }

  const gateway = await ensureGatewayRunning(token);
  if (!gateway.ok) {
    return { ok: false, msg: gateway.msg, prompt: buildCronPrompt() };
  }

  const prompt = buildCronPrompt();
  const jobSpec = {
    name: 'blofin-equity-vertical',
    schedule: 'every 5m',
    // Use custom + Nous inference URL — sk-nous API keys work here.
    // provider:nous requires OAuth device login, not a portal API key.
    provider: 'custom',
    base_url: NOUS_INFERENCE_BASE,
    model: storeData.nous?.model || DEFAULT_NOUS_MODEL,
    deliver: 'local',
    prompt,
  };

  try {
    const list = await hermesApiRequest('GET', '/api/cron/jobs?profile=default', null, token);
    if (list.status === 200 && Array.isArray(list.body)) {
      const existing = list.body.find((job) => job.name === jobSpec.name);
      if (existing?.id) {
        appendLog(`Updating existing cron job: ${existing.id}`, 'info');
        const updated = await hermesApiRequest(
          'PUT',
          `/api/cron/jobs/${encodeURIComponent(existing.id)}?profile=default`,
          { updates: jobSpec },
          token,
        );
        if (updated.status < 300) {
          appendLog('✅ Cron job updated: blofin-equity-vertical (every 5m)', 'success');
          triggerAndConfirmCron(token, existing.id);
          return { ok: true, jobId: existing.id, updated: true };
        }
        const detail = typeof updated.body === 'object'
          ? (updated.body.detail || JSON.stringify(updated.body))
          : String(updated.body);
        appendLog(`⚠ Cron update failed (${updated.status}): ${detail}`, 'warn');
        return { ok: false, msg: detail, prompt };
      }
    }
  } catch (e) {
    appendLog(`  → list cron jobs: ${e.message}`, 'warn');
  }

  try {
    appendLog('Creating cron job via POST /api/cron/jobs', 'info');
    const created = await hermesApiRequest('POST', '/api/cron/jobs?profile=default', jobSpec, token);
    if (created.status < 300) {
      appendLog('✅ Cron configured: blofin-equity-vertical (every 5m)', 'success');
      triggerAndConfirmCron(token, created.body?.id);
      return { ok: true, jobId: created.body?.id, endpoint: '/api/cron/jobs' };
    }
    const detail = typeof created.body === 'object'
      ? (created.body.detail || JSON.stringify(created.body))
      : String(created.body);
    appendLog(`⚠ Cron create failed (${created.status}): ${detail}`, 'warn');
    return { ok: false, msg: detail, prompt };
  } catch (e) {
    appendLog(`⚠ Cron configure failed: ${e.message}`, 'warn');
    return { ok: false, msg: e.message, prompt };
  }
}

async function triggerCronJob(token, jobId) {
  if (!jobId) return { ok: false };
  try {
    appendLog('▶ Triggering cron job now…', 'info');
    const res = await hermesApiRequest(
      'POST',
      `/api/cron/jobs/${encodeURIComponent(jobId)}/trigger?profile=default`,
      null,
      token,
    );
    if (res.status < 300) {
      appendLog('✅ Cron job accepted — waiting for first tick…', 'success');
      return { ok: true };
    }
    appendLog(`⚠ Cron trigger returned ${res.status}`, 'warn');
    return { ok: false, status: res.status };
  } catch (e) {
    appendLog(`⚠ Cron trigger: ${e.message}`, 'warn');
    return { ok: false, error: e.message };
  }
}

function readCronJobRecord(jobId) {
  try {
    const jobsPath = path.join(HERMES_HOME, 'cron', 'jobs.json');
    const parsed = JSON.parse(fs.readFileSync(jobsPath, 'utf8'));
    const jobs = Array.isArray(parsed?.jobs) ? parsed.jobs : [];
    return jobs.find((job) => job.id === jobId) || null;
  } catch {
    return null;
  }
}

function cronTickLooksHealthy(job) {
  const status = String(job?.last_status || '').toLowerCase();
  if (!status) return false;
  if (status === 'error' || status === 'failed' || status.startsWith('blocked')) return false;
  return true;
}

async function triggerAndConfirmCron(token, jobId) {
  if (!jobId) return;
  const before = readCronJobRecord(jobId);
  await triggerCronJob(token, jobId);
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 3000));
    const job = readCronJobRecord(jobId);
    if (!job) continue;
    const ranAgain = job.last_run_at && job.last_run_at !== before?.last_run_at;
    if (!ranAgain) continue;
    if (String(job.state || '').toLowerCase() === 'running') continue;
    if (cronTickLooksHealthy(job)) {
      appendLog(`✅ Cron tick succeeded (${job.last_status || 'ok'})`, 'success');
      return;
    }
    if (job.last_status === 'error') {
      const err = String(job.last_error || 'unknown error');
      const hint = /invalid|blocked|out of funds/i.test(err)
        ? ' — cron did not receive the Nous API key. Save Setup again, then Configure Cron.'
        : '';
      appendLog(`⚠ Cron tick error: ${err}${hint}`, 'error');
      return;
    }
  }
  appendLog('⚠ Cron was triggered but the first tick has not finished yet — check Hermes in a minute', 'warn');
}

function catalogModelEntry(modelName, free) {
  const id = String(modelName || '').trim();
  if (!id) return null;
  return { id, label: free ? `${id} (free)` : id, free: !!free };
}

function preferDefaultFreeModels(free) {
  const list = Array.isArray(free) ? free.filter((m) => m?.id) : [];
  const def = list.find((m) => m.id === DEFAULT_NOUS_MODEL);
  const rest = list.filter((m) => m.id !== DEFAULT_NOUS_MODEL);
  if (def) return [def, ...rest];
  return [{ id: DEFAULT_NOUS_MODEL, label: `${DEFAULT_NOUS_MODEL} (free)`, free: true }, ...rest];
}

async function fetchNousModelCatalog() {
  try {
    const res = await httpsRequest(NOUS_RECOMMENDED_MODELS_URL, { timeout: 15000 });
    const parsed = JSON.parse(res.raw);
    const free = preferDefaultFreeModels(
      (parsed.freeRecommendedModels || [])
        .map((m) => catalogModelEntry(m.modelName, true))
        .filter(Boolean),
    );
    const paidSeen = new Set(free.map((m) => m.id));
    const paid = (parsed.paidRecommendedModels || [])
      .map((m) => catalogModelEntry(m.modelName, false))
      .filter((m) => m && !String(m.id).endsWith(':free') && !paidSeen.has(m.id));
    if (free.length) {
      return {
        ok: true,
        defaultModel: DEFAULT_NOUS_MODEL,
        free,
        paid: paid.length ? paid : FALLBACK_PAID_NOUS_MODELS,
        source: 'live',
      };
    }
  } catch (e) {
    appendLog(`⚠ Nous model catalog: ${e.message} — using fallback list`, 'warn');
  }
  return {
    ok: true,
    defaultModel: DEFAULT_NOUS_MODEL,
    free: FALLBACK_FREE_NOUS_MODELS,
    paid: FALLBACK_PAID_NOUS_MODELS,
    source: 'fallback',
  };
}

// ── Nous Portal credential test ────────────────────────────────────────────
function testNousCredentials(apiKey, model) {
  const key = String(apiKey || '').trim();
  const mdl = normalizeNousModel(model);
  if (!key) return Promise.resolve({ ok: false, error: 'Portal API key is required.' });
  if (!mdl) return Promise.resolve({ ok: false, error: 'Select a Nous model first.' });

  const body = JSON.stringify({
    model: mdl,
    messages: [{ role: 'user', content: 'Reply with exactly: OK' }],
    max_tokens: 16,
    temperature: 0,
  });

  appendLog(`🧪 Testing Nous credentials (${mdl})…`, 'info');

  return new Promise((resolve) => {
    const req = https.request(NOUS_INFERENCE_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${key}`,
        'Content-Length': Buffer.byteLength(body),
        'User-Agent': 'KnightTrader/1.0',
      },
      timeout: 45000,
    }, (res) => {
      let raw = '';
      res.on('data', (chunk) => { raw += chunk; });
      res.on('end', () => {
        let parsed;
        try { parsed = JSON.parse(raw); } catch { parsed = null; }

        if (res.statusCode >= 200 && res.statusCode < 300 && parsed) {
          const reply = parsed?.choices?.[0]?.message?.content?.trim()
            || parsed?.choices?.[0]?.text?.trim()
            || '';
          appendLog(`✅ Nous test passed (${mdl})${reply ? `: ${reply.slice(0, 80)}` : ''}`, 'success');
          resolve({
            ok: true,
            model: mdl,
            reply: reply || '(empty reply — key works)',
            status: res.statusCode,
          });
          return;
        }

        const errMsg = parsed?.error?.message
          || parsed?.message
          || (typeof parsed?.error === 'string' ? parsed.error : null)
          || raw.slice(0, 200)
          || `HTTP ${res.statusCode}`;
        appendLog(`✗ Nous test failed (${res.statusCode}): ${errMsg}`, 'error');
        resolve({ ok: false, error: errMsg, status: res.statusCode, model: mdl });
      });
    });

    req.on('timeout', () => {
      req.destroy();
      appendLog('✗ Nous test timed out after 45s', 'error');
      resolve({ ok: false, error: 'Request timed out after 45 seconds.' });
    });
    req.on('error', (e) => {
      appendLog(`✗ Nous test error: ${e.message}`, 'error');
      resolve({ ok: false, error: e.message });
    });
    req.write(body);
    req.end();
  });
}

// ── Blofin API credential test ─────────────────────────────────────────────
function signBlofinRequest(secret, method, path, timestamp, nonce, body = '') {
  const prehash = `${path}${method}${timestamp}${nonce}${body}`;
  const hex = crypto.createHmac('sha256', secret).update(prehash).digest('hex');
  return Buffer.from(hex, 'utf8').toString('base64');
}

function httpsRequest(urlStr, { method = 'GET', headers = {}, timeout = 45000 } = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const req = https.request({
      hostname: url.hostname,
      port: url.port || 443,
      path: url.pathname + url.search,
      method,
      headers: {
        'User-Agent': 'KnightTrader/1.0',
        Accept: 'application/json',
        ...headers,
      },
      timeout,
    }, (res) => {
      let raw = '';
      res.on('data', (chunk) => { raw += chunk; });
      res.on('end', () => resolve({ status: res.statusCode, raw }));
    });
    req.on('timeout', () => { req.destroy(); reject(new Error('Request timed out after 45 seconds.')); });
        req.on('error', reject);
    req.end();
  });
}

function summarizeBlofinBalances(data) {
  if (!Array.isArray(data) || data.length === 0) return '';
  const usdt = data.find((row) => {
    const ccy = String(row?.currency || row?.ccy || row?.coin || '').toUpperCase();
    return ccy === 'USDT';
  });
  if (!usdt) return `${data.length} balance row(s)`;
  const avail = usdt.available ?? usdt.availBal ?? usdt.balance ?? usdt.equity;
  return avail != null ? `USDT available: ${avail}` : 'USDT balance found';
}

function testBlofinCredentials({ apiKey, secretKey, passphrase, demoMode }) {
  const key = String(apiKey || '').trim();
  const secret = String(secretKey || '').trim();
  const pass = String(passphrase || '').trim();
  const baseUrl = demoMode ? BLOFIN_DEMO_URL : BLOFIN_LIVE_URL;
  const modeLabel = demoMode ? 'DEMO' : 'LIVE';

  if (!key || !secret || !pass) {
    return Promise.resolve({ ok: false, error: 'API key, secret key, and passphrase are all required.' });
  }

  const path = '/api/v1/asset/balances?accountType=futures';
  const timestamp = String(Date.now());
  const nonce = crypto.randomUUID();
  const signature = signBlofinRequest(secret, 'GET', path, timestamp, nonce);

  appendLog(`🧪 Testing Blofin credentials (${modeLabel})…`, 'info');

  return httpsRequest(`${baseUrl}${path}`, {
    method: 'GET',
    headers: {
      'ACCESS-KEY': key,
      'ACCESS-SIGN': signature,
      'ACCESS-TIMESTAMP': timestamp,
      'ACCESS-NONCE': nonce,
      'ACCESS-PASSPHRASE': pass,
    },
  }).then(({ status, raw }) => {
    const trimmed = raw.trim();
    if (trimmed.startsWith('<') || /<!DOCTYPE/i.test(trimmed)) {
      const err = 'Got HTML instead of JSON — likely Cloudflare/WAF block. Check VPN country or transport.';
      appendLog(`✗ Blofin test failed: ${err}`, 'error');
      return { ok: false, error: err, status, mode: modeLabel };
    }

    let parsed;
    try { parsed = JSON.parse(raw); } catch {
      const err = trimmed.slice(0, 200) || `HTTP ${status}`;
      appendLog(`✗ Blofin test failed: ${err}`, 'error');
      return { ok: false, error: err, status, mode: modeLabel };
    }

    const code = String(parsed?.code ?? '');
    if (code === '0') {
      const summary = summarizeBlofinBalances(parsed?.data);
      appendLog(`✅ Blofin test passed (${modeLabel})${summary ? `: ${summary}` : ''}`, 'success');
      return { ok: true, mode: modeLabel, summary: summary || 'Authenticated successfully', status, data: parsed?.data };
    }

    const errMsg = parsed?.msg || parsed?.message || `API error code ${code || status}`;
    appendLog(`✗ Blofin test failed (${modeLabel}): ${errMsg}`, 'error');
    return { ok: false, error: errMsg, status, mode: modeLabel, code };
  }).catch((e) => {
    appendLog(`✗ Blofin test error: ${e.message}`, 'error');
    return { ok: false, error: e.message, mode: modeLabel };
  });
}

// ── Windows Defender exclusion (prevents Commando.A!ml false positive) ─────
function addDefenderExclusion() {
  return new Promise((resolve) => {
    appendLog('🛡 Adding Windows Defender exclusion for sandboxed Hermes folder...', 'info');
    appendLog('  A UAC admin prompt may appear — click Yes to allow.', 'warn');

    const excludePaths = [HERMES_HOME].map(p => `'${p}'`).join(',');
    const psCmd = `Add-MpPreference -ExclusionPath ${excludePaths} -ExclusionProcess 'hermes.exe','uv.exe'`;
    const elevatedArgs = `-NoProfile -ExecutionPolicy Bypass -Command "${psCmd}"`;
    const wrapCmd = `Start-Process powershell -Verb RunAs -Wait -ArgumentList '${elevatedArgs.replace(/'/g, "''")}'`;

    const proc = spawn('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', wrapCmd]);
    proc.stdout.on('data', d => appendLog(d.toString().trim(), 'info'));
    proc.stderr.on('data', d => appendLog(d.toString().trim(), 'warn'));
    proc.on('close', (code) => {
      if (code === 0) {
        appendLog('✅ Defender exclusion added. Safe to install Hermes now.', 'success');
        resolve({ ok: true });
      } else {
        appendLog('⚠ Could not auto-add exclusion (code ' + code + '). Add manually in Windows Security → Exclusions.', 'warn');
        resolve({ ok: false, code, manual: HERMES_HOME });
      }
    });
    proc.on('error', (e) => resolve({ ok: false, error: e.message }));
  });
}

// ── IPC ────────────────────────────────────────────────────────────────────
function factoryResetLocalState() {
  const userData = app.getPath('userData');
  const targets = [
    { path: STORE_PATH, label: 'encrypted credentials' },
    { path: HERMES_HOME, label: 'Hermes sandbox' },
    { path: path.join(userData, 'blohunter-storage.json'), label: 'trading desk cache' },
    { path: path.join(userData, 'Partitions'), label: 'webview cache' },
  ];
  const errors = [];
  for (const item of targets) {
    try {
      if (fs.existsSync(item.path)) {
        fs.rmSync(item.path, { recursive: true, force: true });
        appendLog(`🧹 Removed ${item.label}`, 'warn');
      }
    } catch (e) {
      errors.push(`${item.label}: ${e.message}`);
    }
  }
  storeData = JSON.parse(JSON.stringify(DEFAULTS));
  blohunterBridge = null;
  dashboardSessionToken = null;
  dashboardReady = false;
  return { ok: errors.length === 0, errors };
}

function registerIPC() {
  ipcMain.handle('get-credentials',   () => storeData);
  ipcMain.handle('save-credentials', async (_e, data) => {
    storeData = migrateStoreData({ ...storeData, ...data });
    saveStore(storeData);
    try {
      let token = null;
      if (await probeDashboardPort()) {
        token = await fetchDashboardSessionToken().catch(() => null);
      }
      await syncHermesCredentials(token, { restartGateway: !!token });
    } catch (e) {
      appendLog(`⚠ Hermes .env sync on save: ${e.message}`, 'warn');
    }
    try {
      await syncBlohunterCredentials();
    } catch (e) {
      appendLog(`⚠ BloHunter cred sync on save: ${e.message}`, 'warn');
    }
    return { ok: true };
  });
  ipcMain.handle('write-compendium',  () => { try { const p = writeCompendiumFile(); appendLog(`✅ Compendium written: ${p}`, 'success'); return { ok: true, path: p }; } catch (e) { return { ok: false, error: e.message }; } });
  ipcMain.handle('get-compendium-path', () => getCompendiumPath());
  ipcMain.handle('test-nous-credentials', (_e, { apiKey, model }) => testNousCredentials(apiKey, model));
  ipcMain.handle('get-nous-models', () => fetchNousModelCatalog());
  ipcMain.handle('test-blofin-credentials', (_e, creds) => testBlofinCredentials(creds));
  ipcMain.handle('pick-nous-credential-file', () => pickCredentialFile('nous'));
  ipcMain.handle('pick-blofin-credential-file', () => pickCredentialFile('blofin'));
  ipcMain.handle('check-hermes',      () => checkHermesInstalled());
  ipcMain.handle('install-hermes',    () => installHermes());
  ipcMain.handle('add-defender-exclusion', () => addDefenderExclusion());
  ipcMain.handle('start-dashboard',   () => startHermesDashboard());
  ipcMain.handle('stop-dashboard',    () => stopHermesDashboard());
  ipcMain.handle('get-dashboard-status', () => getDashboardStatus());
  ipcMain.handle('configure-cron',    () => configureCron());
  ipcMain.handle('get-cron-prompt',   () => buildCronPrompt());
  ipcMain.handle('get-hermes-home',   () => HERMES_HOME);
  ipcMain.handle('get-logs',          () => logBuffer);
  ipcMain.handle('clear-logs',        () => { logBuffer = []; return { ok: true }; });
  ipcMain.handle('open-external',     (_e, url) => shell.openExternal(url));

  ipcMain.handle('get-blohunter-preload-path', () => pathToFileURL(path.join(__dirname, 'blohunter-preload.js')).href);
  ipcMain.handle('attach-trading-webview', (_e, webContentsId) => {
    const wc = webContents.fromId(webContentsId);
    if (wc) getBlohunterBridge().setWebContents(wc);
    return { ok: !!wc };
  });
  ipcMain.handle('get-trading-status', () => getBlohunterBridge().getStatus());
  ipcMain.handle('start-trading-dashboard', async () => {
    const bridge = getBlohunterBridge();
    const result = await bridge.start({
      apiKey: storeData.blofin?.apiKey,
      secretKey: storeData.blofin?.secretKey,
      passphrase: storeData.blofin?.passphrase,
      demoMode: storeData.blofin?.demoMode,
    });
    if (!result.ok) appendLog(`⚠ Trading dashboard: ${result.error}`, 'warn');
    else appendLog('✅ BloHunter trading dashboard ready', 'success');
    return result;
  });
  ipcMain.handle('stop-trading-dashboard', () => getBlohunterBridge().stop());
  ipcMain.handle('bh-runtime-send', async (_e, msg) => {
    const bridge = getBlohunterBridge();
    try {
      await bridge.ensureBackground();
    } catch (err) {
      return { ok: false, msg: err?.message || 'Trading background failed to start' };
    }
    const response = await bridge.dispatchRuntimeMessage(msg);
    if (response === undefined) {
      return { ok: false, msg: 'No BloHunter handler answered this request' };
    }
    return response;
  });
  ipcMain.handle('bh-storage-get', (_e, keys) => {
    getBlohunterBridge().storage.load();
    return getBlohunterBridge().storage.pick('local', keys);
  });
  ipcMain.handle('bh-storage-set', async (_e, items) => {
    getBlohunterBridge().storage.load();
    return getBlohunterBridge().storage.setArea('local', items);
  });
  ipcMain.handle('bh-storage-remove', (_e, keys) => {
    getBlohunterBridge().storage.load();
    return getBlohunterBridge().storage.removeArea('local', keys);
  });
  ipcMain.handle('bh-storage-get-session', (_e, keys) => {
    getBlohunterBridge().storage.load();
    return getBlohunterBridge().storage.pick('session', keys);
  });
  ipcMain.handle('bh-storage-set-session', async (_e, items) => {
    getBlohunterBridge().storage.load();
    return getBlohunterBridge().storage.setArea('session', items);
  });
  ipcMain.handle('bh-storage-remove-session', (_e, keys) => {
    getBlohunterBridge().storage.load();
    return getBlohunterBridge().storage.removeArea('session', keys);
  });

  ipcMain.on('window-minimize', () => mainWindow?.minimize());
  ipcMain.on('window-maximize', () => mainWindow?.isMaximized() ? mainWindow.restore() : mainWindow?.maximize());
  ipcMain.on('window-close',    () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.hide();
      buildTray();
      appendLog('🧩 Minimized to system tray — double-click tray icon to restore', 'info');
    }
  });
}

// ── Window ─────────────────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1060, height: 740, minWidth: 860, minHeight: 600,
    frame: false, backgroundColor: '#090c10', show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, nodeIntegration: false,
      webviewTag: true
    },
    title: 'KnightTrader'
  });
  mainWindow.loadFile('renderer/index.html');
  mainWindow.once('ready-to-show', () => { mainWindow.show(); mainWindow.focus(); });
  mainWindow.on('closed', () => { mainWindow = null; });
  mainWindow.on('minimize', () => {
    mainWindow.hide();
    buildTray();
  });
}

// ── Suppress harmless Chromium GPU cache console noise ─────────────────────
app.commandLine.appendSwitch('disable-gpu-shader-disk-cache');
app.commandLine.appendSwitch('disable-features', 'CalculateNativeWinOcclusion');
app.commandLine.appendSwitch('log-level', '3'); // errors only, not cache warnings

// ── App lifecycle ──────────────────────────────────────────────────────────
function handleBhProtocol(request) {
  const bridge = getBlohunterBridge();
  const served = bridge.serveProtocolRequest(request.url);
  if (!served.ok) {
    return new Response(served.body || 'Not found', { status: served.status || 404 });
  }
  try {
    let data = fs.readFileSync(served.filePath);
    if (served.injectSkin) {
      let html = data.toString('utf8');
      html = html.replace(/<title>BloHunter Connect<\/title>/i, '<title>KnightTrader</title>');
      if (!html.includes('__kt__/kt-skin.css')) {
        html = html.replace(
          '</head>',
          [
            '    <link rel="preconnect" href="https://fonts.googleapis.com" />',
            '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />',
            '    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />',
            '    <link rel="stylesheet" href="bh://local/__kt__/kt-skin.css" />',
            '    <script src="bh://local/__kt__/kt-skin.js" defer></script>',
            '  </head>',
          ].join('\n'),
        );
      }
      data = Buffer.from(html, 'utf8');
    }
    return new Response(data, {
      status: 200,
      headers: {
        'Content-Type': served.contentType,
        'Access-Control-Allow-Origin': '*',
      },
    });
  } catch (err) {
    return new Response(err.message || 'Read failed', { status: 500 });
  }
}

function attachBhProtocol(ses) {
  if (!ses || ses.__ktBhProtocol) return;
  ses.__ktBhProtocol = true;
  ses.protocol.handle('bh', handleBhProtocol);
}

function setupAutoUpdater() {
  if (!autoUpdater) return;
  autoUpdater.autoDownload = true;
  autoUpdater.setFeedURL({
    provider: 'github',
    owner: 'mknight2690-sys',
    repo: 'KnightTrader-BloFin',
    releaseType: 'release',
  });
  autoUpdater.on('update-available', (info) => {
    appendLog(`⬆ Update available: ${info.version}`, 'success');
    for (const wc of webContents.getAllWebContents()) wc.send('update-available', info);
  });
  autoUpdater.on('update-not-available', (info) => {
    appendLog(`✅ Up to date: ${info.version}`, 'info');
    for (const wc of webContents.getAllWebContents()) wc.send('update-not-available', info);
  });
  autoUpdater.on('update-downloaded', (info) => {
    appendLog(`⬇ Update ready: ${info.version}`, 'success');
    for (const wc of webContents.getAllWebContents()) wc.send('update-downloaded', info);
  });
  autoUpdater.on('error', (err) => {
    appendLog(`⚠ Auto-update error: ${err?.message || err}`, 'warn');
    for (const wc of webContents.getAllWebContents()) wc.send('update-error', err);
  });
  setTimeout(() => {
    appendLog('🔎 Checking for updates…', 'info');
    autoUpdater.checkForUpdates().catch((err) => {
      appendLog(`⚠ Update check failed: ${err?.message || err}`, 'warn');
    });
  }, 5000);
}

app.whenReady().then(async () => {
  attachBhProtocol(session.defaultSession);
  attachBhProtocol(session.fromPartition('persist:blohunter-trading'));

  registerIPC();
  createWindow();
  appendLog(`🚀 KnightTrader started. Hermes sandbox: ${HERMES_HOME}`, 'success');
  syncHermesCredentials(null).catch((e) => {
    appendLog(`ℹ Hermes credential sync deferred: ${e.message}`, 'info');
  });
  const bhRoot = getBlohunterBridge().getConnectRoot();
  if (bhRoot) appendLog(`📈 BloHunter Connect: ${bhRoot}`, 'info');
  else appendLog('⚠ BloHunter Connect not found — Trading tab needs Downloads\\blohunter-connect', 'warn');
  startBlohunterHotReloadWatcher();
  setupAutoUpdater();
});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
