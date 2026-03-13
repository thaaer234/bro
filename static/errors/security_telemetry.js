(function () {
  function now() { return Date.now(); }

  function createTelemetryClient(options) {
    const config = Object.assign({
      endpoint: '/security/api/telemetry/',
      consent: false,
      sampleTyping: true,
      trackFiles: true,
      sessionKey: 'security-telemetry-client-id'
    }, options || {});

    const state = {
      pageHistory: [],
      clickPath: [],
      typingIntervals: [],
      lastKeyAt: null,
      fileMetadata: [],
      clientId: localStorage.getItem(config.sessionKey) || crypto.randomUUID(),
    };
    localStorage.setItem(config.sessionKey, state.clientId);

    function pushPage() {
      state.pageHistory.push({ path: location.pathname, at: new Date().toISOString() });
      state.pageHistory = state.pageHistory.slice(-20);
    }

    function handleClick(event) {
      const target = event.target.closest('button,a,input,label,[data-security-track]');
      if (!target) return;
      state.clickPath.push({
        tag: target.tagName,
        id: target.id || '',
        name: target.getAttribute('name') || '',
        path: location.pathname,
        at: new Date().toISOString()
      });
      state.clickPath = state.clickPath.slice(-50);
    }

    function handleKeydown() {
      if (!config.sampleTyping) return;
      const current = now();
      if (state.lastKeyAt) {
        state.typingIntervals.push(current - state.lastKeyAt);
        state.typingIntervals = state.typingIntervals.slice(-40);
      }
      state.lastKeyAt = current;
    }

    function bindUploads() {
      if (!config.trackFiles) return;
      document.querySelectorAll('input[type="file"]').forEach(function (input) {
        input.addEventListener('change', function () {
          state.fileMetadata = Array.from(input.files || []).map(function (file) {
            return { name: file.name, size: file.size, type: file.type || '' };
          }).slice(-20);
        });
      });
    }

    function typingProfile() {
      if (!state.typingIntervals.length) return {};
      const avg = state.typingIntervals.reduce((a, b) => a + b, 0) / state.typingIntervals.length;
      return {
        averageMs: Math.round(avg),
        sampleSize: state.typingIntervals.length,
        suspicious: avg < 35
      };
    }

    async function captureScreenshot() {
      if (typeof window.html2canvas !== 'function') {
        return '';
      }
      try {
        const canvas = await window.html2canvas(document.body, {
          useCORS: true,
          backgroundColor: '#ffffff',
          scale: 0.6,
          logging: false
        });
        return canvas.toDataURL('image/jpeg', 0.4);
      } catch (error) {
        return '';
      }
    }

    async function send(summary) {
      if (!config.consent) return;
      const screenshot = await captureScreenshot();
      const payload = {
        consent: true,
        summary: summary || 'Periodic consent-based telemetry snapshot',
        clientId: state.clientId,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
        platform: navigator.platform || '',
        touchPoints: navigator.maxTouchPoints || 0,
        screen: `${window.screen.width}x${window.screen.height}`,
        pageHistory: state.pageHistory,
        clickPath: state.clickPath,
        typingProfile: typingProfile(),
        fileMetadata: state.fileMetadata,
        screenshot: screenshot,
      };
      const csrf = document.querySelector('[name=csrfmiddlewaretoken]');
      await fetch(config.endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf ? csrf.value : '',
        },
        body: JSON.stringify(payload)
      });
    }

    pushPage();
    document.addEventListener('click', handleClick, true);
    document.addEventListener('keydown', handleKeydown, true);
    bindUploads();

    return { send };
  }

  window.SecurityTelemetry = { create: createTelemetryClient };
})();
