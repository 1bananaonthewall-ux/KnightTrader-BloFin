const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');

async function loadSignalHelper() {
  const mod = await import(
    pathToFileURL(
      path.join(
        require('os').homedir(),
        'Downloads',
        'blohunter-connect',
        'src',
        'shared',
        'syncStatusPresentation.js'
      )
    ).href
  );
  return mod.getV3DashboardSignalStatus;
}

function summarize(label, data) {
  const profile = data?.profile || {};
  return {
    label,
    ok: data?.ok,
    equity: data?.balances?.totalEquity,
    available: data?.balances?.totalAvailable,
    exposure: data?.exposure?.totalMargin,
    openCount: data?.exposure?.openCount,
    dailyPnl: data?.performance?.dailyPnl,
    monthlyPnl: data?.performance?.monthlyPnl,
    equityHistory: (data?.equityHistory || []).length,
    activity: (data?.recentActivity || [])[0]?.type || '',
    errorMessage: data?.errorMessage || '',
    policy: profile.serverPolicyStatus,
    snapshot: profile.gatewayV3SnapshotStatus,
    capabilities: profile.gatewayV3CapabilitiesStatus,
    awaiting: profile.signalAwaitingSnapshot,
    connected: profile.signalConnected,
    trading: profile.tradingEnabled,
    blofinOk: profile.blofinApiOk,
    blofinFresh: profile.blofinApiFresh,
  };
}

(async () => {
  console.log('node', process.versions.node, 'electron', process.versions.electron || 'none');
  const { installEd25519Subtle } = require('./blohunter/ed25519-polyfill');
  installEd25519Subtle();
  try {
    await crypto.subtle.importKey(
      'spki',
      Buffer.from(
        'MCowBQYDK2VwAyEAg2uVEsECMi+pBln29Fl+qENa4+Ny15ef5OUOZSjN7dg=',
        'base64'
      ),
      'Ed25519',
      false,
      ['verify']
    );
    console.log('ed25519-import: ok');
  } catch (err) {
    console.log('ed25519-import: FAIL', err.message);
    process.exit(1);
  }

  const userDataPath = fs.mkdtempSync(path.join(require('os').tmpdir(), 'kt-desk-'));
  const liveStore = path.join(process.env.APPDATA, 'knight-trader', 'blohunter-storage.json');
  fs.copyFileSync(liveStore, path.join(userDataPath, 'blohunter-storage.json'));
  const store = JSON.parse(fs.readFileSync(path.join(userDataPath, 'blohunter-storage.json'), 'utf8'));
  const creds = store.session || {};
  if (!creds.apiKey || !creds.secret || !creds.passphrase) {
    console.log('missing session creds');
    process.exit(1);
  }

  const { BlohunterBridge } = require('./blohunter-bridge');
  const logs = [];
  const bridge = new BlohunterBridge({
    userDataPath,
    log: (m) => {
      const line = String(m);
      logs.push(line);
      if (/SSE|handshake|Equity|listeners|Desk/i.test(line)) console.log('[log]', line);
    },
  });

  const started = await bridge.start({
    apiKey: creds.apiKey,
    secretKey: creds.secret,
    passphrase: creds.passphrase,
    demoMode: false,
  });
  console.log('started', started.ok, started.url || started.error);

  const getSignal = await loadSignalHelper();
  let last = null;
  let signalText = '';
  for (let i = 0; i < 20; i += 1) {
    await new Promise((r) => setTimeout(r, 1000));
    const snap = await bridge.dispatchRuntimeMessage({ type: 'get-dashboard-data' });
    last = snap?.data || {};
    const status = getSignal(last.profile || {}, Date.now());
    signalText = status?.signalText || 'none';
    const local = bridge.storage.pick('local', [
      'server_policy_status',
      'gateway_v3_snapshot_status',
      'gateway_v3_capabilities_status',
      'sse_awaiting_snapshot',
      'sse_signal_phase',
    ]);
    console.log(
      `t=${i + 1}s signal=${signalText} equity=${last.balances?.totalEquity} avail=${last.balances?.totalAvailable} hist=${(last.equityHistory || []).length} policy=${local.server_policy_status} snap=${local.gateway_v3_snapshot_status} cap=${local.gateway_v3_capabilities_status} awaiting=${local.sse_awaiting_snapshot} phase=${local.sse_signal_phase}`
    );
    if (
      (signalText === 'operational' || signalText === 'connected') &&
      Number(last.balances?.totalEquity) > 0 &&
      Number(last.balances?.totalAvailable) > 0 &&
      (last.equityHistory || []).length >= 2
    ) {
      break;
    }
  }

  const summary = summarize('final', last);
  summary.signalText = signalText;
  summary.sseConnected = bridge.sse?.isConnected?.();
  console.log(JSON.stringify(summary, null, 2));

  const pass =
    (signalText === 'operational' || signalText === 'connected') &&
    Number(summary.equity) > 0 &&
    Number(summary.available) > 0 &&
    summary.equityHistory >= 2 &&
    summary.ok !== false &&
    !summary.awaiting &&
    (summary.snapshot === 'verified' || summary.snapshot === 'snapshot_verified');

  try { await bridge.stop(); } catch {}
  process.exit(pass ? 0 : 2);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
