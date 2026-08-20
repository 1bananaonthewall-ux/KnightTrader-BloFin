(() => {
  const releaseUrl = 'https://github.com/mknig/hermes-trader/releases/latest';
  const platforms = {
    windows: {
      label: 'Download for Windows',
      note: '.exe installer — Windows 10/11',
      href: releaseUrl,
      macVisible: false,
    },
    mac: {
      label: 'Open macOS build guide',
      note: 'Build locally with Electron — see below',
      href: '#getting',
      macVisible: true,
    },
  };

  const btnDownload = document.getElementById('btn-download');
  const downloadNote = document.getElementById('download-note');
  const macNote = document.getElementById('mac-note');
  const buttons = document.querySelectorAll('.platform-btn');

  function selectPlatform(key) {
    const data = platforms[key];
    if (!data || !btnDownload || !downloadNote) return;
    buttons.forEach((btn) => {
      const active = btn.dataset.platform === key;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', String(active));
    });
    btnDownload.textContent = data.label;
    downloadNote.textContent = data.note;
    if (data.href && btnDownload.getAttribute('href') !== data.href) {
      btnDownload.setAttribute('href', data.href);
    }
    if (macNote) {
      macNote.classList.toggle('hidden', !data.macVisible);
    }
  }

  buttons.forEach((btn) => {
    btn.addEventListener('click', () => selectPlatform(btn.dataset.platform));
  });

  selectPlatform('windows');
})();
