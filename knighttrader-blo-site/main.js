(() => {
  const releaseBase = 'https://github.com/mknight2690-sys/KnightTrader-BloFin';
  const releaseApiUrl = `${releaseBase}/releases/latest`;
  let windowsUrl = `${releaseBase}/releases/latest`;
  let macUrl = `${releaseBase}/releases/latest`;
  const btnWindows = document.getElementById('btn-download-windows');
  const btnMac = document.getElementById('btn-download-mac');
  const downloadNote = document.getElementById('download-note');
  const buttons = document.querySelectorAll('.platform-btn');

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
    return assets.find((asset) => pattern.test(asset.name));
  }

  async function updateDownloadLinks() {
    const release = await fetchLatestRelease();
    if (release?.assets?.length) {
      const windowsAsset = findAsset(release.assets, /\.exe$/i);
      const macAsset = findAsset(release.assets, /\.dmg$/i);
      if (windowsAsset?.browser_download_url) {
        windowsUrl = windowsAsset.browser_download_url;
      }
      if (macAsset?.browser_download_url) {
        macUrl = macAsset.browser_download_url;
      }
    }
  }

  async function forceDownload(url, filename) {
    try {
      const res = await fetch(url, { mode: 'cors' });
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename || '';
      a.target = '_blank';
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(blobUrl);
      }, 0);
    } catch {
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || '';
      a.target = '_blank';
      document.body.appendChild(a);
      a.click();
      setTimeout(() => document.body.removeChild(a), 0);
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
      btnWindows.setAttribute('href', isMac ? '' : windowsUrl);
      btnWindows.setAttribute('download', isMac ? '' : 'KnightTrader-BloFin-Setup.exe');
      btnWindows.textContent = 'Download for Windows';
    }
    if (btnMac) {
      btnMac.classList.toggle('hidden', !isMac);
      btnMac.setAttribute('href', isMac ? macUrl : '');
      btnMac.setAttribute('download', isMac ? 'KnightTrader-BloFin.dmg' : '');
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

  if (btnWindows) {
    btnWindows.addEventListener('click', (e) => {
      e.preventDefault();
      const href = btnWindows.getAttribute('href');
      if (!href) return;
      forceDownload(href, 'KnightTrader-BloFin-Setup.exe');
    });
  }

  if (btnMac) {
    btnMac.addEventListener('click', (e) => {
      e.preventDefault();
      const href = btnMac.getAttribute('href');
      if (!href) return;
      forceDownload(href, 'KnightTrader-BloFin.dmg');
    });
  }

  updateDownloadLinks().then(() => selectPlatform('windows'));
})();
