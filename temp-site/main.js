(() => {
  const owner = '1bananaonthewall-ux';
  const repo = 'KnightTrader-BloFin';
  const releaseApiUrl = `https://api.github.com/repos/${owner}/${repo}/releases/latest`;
  const releaseWebBase = `https://github.com/${owner}/${repo}/releases`;
  const windowsAssetUrl = 'https://github.com/1bananaonthewall-ux/KnightTrader-BloFin/releases/download/v1.0.9/KnightTrader.Blofin.Setup.1.0.9.exe';
  const macAssetUrl = 'https://github.com/1bananaonthewall-ux/KnightTrader-BloFin/releases/download/v1.0.9/KnightTrader-Blofin-1.0.9-arm64.dmg';
  let windowsUrl = windowsAssetUrl;
  let macUrl = macAssetUrl;
  const ALLOWED_USERS = [
    { email: 'tails123@gmail.com', password: 'blohunterdaddy1!' },
    { email: '1bananaonthewall@gmail.com', password: 'Carterjaxon15!' },
  ];
  const STRIPE_CHECKOUT_URL = 'https://buy.stripe.com/cNi3cwe6Wb0oc991JOe3e0b';
  const SESSION_KEY = 'kt-site-session';

  function normalizeEmail(value) { return String(value || '').trim().toLowerCase(); }
  function isAllowedUser(email, password) {
    const targetEmail = normalizeEmail(email);
    const targetPassword = String(password || '');
    return ALLOWED_USERS.some((u) => normalizeEmail(u.email) === targetEmail && u.password === targetPassword);
  }
  function getSession() {
    try { return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); } catch { return null; }
  }
  function saveSession(session) { try { localStorage.setItem(SESSION_KEY, JSON.stringify(session)); } catch {} }
  function clearSession() { try { localStorage.removeItem(SESSION_KEY); } catch {} }
  function isLoggedIn() {
    const session = getSession();
    return !!session?.email && !!session?.password && isAllowedUser(session.email, session.password);
  }

  const btnWindows = document.getElementById('btn-download-windows');
  const btnMac = document.getElementById('btn-download-mac');
  const downloadNote = document.getElementById('download-note');
  const buttons = document.querySelectorAll('.platform-btn');
  const siteLoginError = document.getElementById('site-login-error');
  const siteForgotError = document.getElementById('site-forgot-error');
  const siteForgotSuccess = document.getElementById('site-forgot-success');

  function setSiteLoginError(message) { if (siteLoginError) siteLoginError.textContent = message || ''; }
  function setSiteForgotError(message) { if (siteForgotError) siteForgotError.textContent = message || ''; }
  function setSiteForgotSuccess(message) { if (siteForgotSuccess) siteForgotSuccess.textContent = message || ''; }

  async function fetchLatestRelease() {
    try {
      const res = await fetch(releaseApiUrl, {
        headers: { Accept: 'application/vnd.github+json' },
      });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }

  function findAsset(assets, pattern) {
    if (!Array.isArray(assets)) return null;
    return assets.find((asset) => pattern.test(asset.name)) || null;
  }

  async function updateDownloadLinks() {
    const release = await fetchLatestRelease();
    if (release?.assets?.length) {
      const windowsAsset = findAsset(release.assets, /KnightTrader[-.]Blofin[-.]Setup.*\.exe$/i)
        || findAsset(release.assets, /\.exe$/i);
      const macAsset = findAsset(release.assets, /KnightTrader[-.]Blofin.*\.dmg$/i)
        || findAsset(release.assets, /\.dmg$/i);
      if (windowsAsset?.browser_download_url) {
        windowsUrl = windowsAsset.browser_download_url;
      }
      if (macAsset?.browser_download_url) {
        macUrl = macAsset.browser_download_url;
      }
    }
  }

  function triggerDownload(url) {
    try {
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch {
      // ignore and fall through
    }
  }

  function selectPlatform(key) {
    const isMac = key === 'mac';
    buttons.forEach((btn) => {
      const active = btn.dataset.platform === key;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', String(active));
    });
    if (btnWindows) {
      btnWindows.classList.toggle('hidden', isMac);
      btnWindows.textContent = 'Download for Windows';
    }
    if (btnMac) {
      btnMac.classList.toggle('hidden', !isMac);
      btnMac.textContent = 'Download for Mac';
    }
    if (downloadNote) {
      downloadNote.textContent = isMac
        ? 'Mac: download the KT BloFin .dmg directly.'
        : 'Windows: download the KT BloFin .exe installer directly.';
    }
  }

  buttons.forEach((btn) => {
    btn.addEventListener('click', () => selectPlatform(btn.dataset.platform));
  });

  function bindDownloads() {
    if (btnWindows) {
      btnWindows.onclick = (e) => {
        e.preventDefault();
        if (!isLoggedIn()) {
          setSiteLoginError('Sign in first to download.');
          return;
        }
        triggerDownload(windowsUrl);
      };
    }
    if (btnMac) {
      btnMac.onclick = (e) => {
        e.preventDefault();
        if (!isLoggedIn()) {
          setSiteLoginError('Sign in first to download.');
          return;
        }
        triggerDownload(macUrl);
      };
    }
  }

  bindDownloads();

  const formSiteLogin = document.getElementById('form-site-login');
  const formSiteForgot = document.getElementById('form-site-forgot');
  const btnSiteForgot = document.getElementById('btn-site-forgot');
  const btnSiteForgotBack = document.getElementById('btn-site-forgot-back');
  const btnStartCheckout = document.getElementById('btn-start-checkout');

  const subscribeButtons = [
    document.getElementById('btn-subscribe-top'),
    document.getElementById('btn-subscribe-hero'),
    document.getElementById('btn-subscribe'),
    document.getElementById('btn-subscribe-pricing'),
  ];

  subscribeButtons.forEach((btn) => {
    if (btn) {
      btn.addEventListener('click', () => {
        window.open(STRIPE_CHECKOUT_URL, '_blank', 'noopener,noreferrer');
      });
    }
  });

  if (formSiteLogin) {
    formSiteLogin.addEventListener('submit', (e) => {
      e.preventDefault();
      setSiteLoginError('');
      const email = document.getElementById('site-email')?.value || '';
      const password = document.getElementById('site-password')?.value || '';
      if (!email || !password) {
        setSiteLoginError('Enter both email and password.');
        return;
      }
      if (!isAllowedUser(email, password)) {
        setSiteLoginError('Invalid email or password.');
        return;
      }
      saveSession({ email: normalizeEmail(email), password });
      setSiteLoginError('');
      setSiteLoginError('Signed in. You can download now.');
    });
  }

  if (btnSiteForgot) {
    btnSiteForgot.addEventListener('click', () => {
      setSiteLoginError('');
      if (formSiteLogin) formSiteLogin.classList.add('hidden');
      if (formSiteForgot) formSiteForgot.classList.remove('hidden');
    });
  }

  if (btnSiteForgotBack) {
    btnSiteForgotBack.addEventListener('click', () => {
      setSiteForgotError('');
      setSiteForgotSuccess('');
      if (formSiteForgot) formSiteForgot.classList.add('hidden');
      if (formSiteLogin) formSiteLogin.classList.remove('hidden');
    });
  }

  if (formSiteForgot) {
    formSiteForgot.addEventListener('submit', (e) => {
      e.preventDefault();
      setSiteForgotError('');
      setSiteForgotSuccess('');
      const email = normalizeEmail(document.getElementById('site-forgot-email')?.value || '');
      if (!email) {
        setSiteForgotError('Enter the email for your account.');
        return;
      }
      if (!ALLOWED_USERS.some((u) => normalizeEmail(u.email) === email)) {
        setSiteForgotSuccess('If an account exists, a reset link has been sent.');
        return;
      }
      setSiteForgotSuccess('Reset link sent. Check your email.');
    });
  }

  if (btnStartCheckout) {
    btnStartCheckout.addEventListener('click', () => {
      window.open(STRIPE_CHECKOUT_URL, '_blank', 'noopener,noreferrer');
    });
  }

  updateDownloadLinks().then(() => selectPlatform('windows'));
})();
