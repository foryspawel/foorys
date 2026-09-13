(function () {
  "use strict";

  if (!location.hash.startsWith("#e2itcf")) return;

  function value(name) {
    const separator = location.hash.indexOf("_sep_");
    const query = separator >= 0 ? location.hash.slice(separator + 5) : location.hash.slice(1);
    const params = new URLSearchParams(query);
    const raw = params.get(name);
    try { return raw ? decodeURIComponent(raw) : ""; } catch (_error) { return raw || ""; }
  }

  const callbackUrl = value("u");
  const captchaId = value("c");
  if (!callbackUrl || !captchaId) return;

  let challengeWasVisible = false;
  let delivered = false;

  function challengeVisible() {
    const form = document.querySelector("#challenge-form");
    return Boolean(form && form.getClientRects().length);
  }

  function deliver() {
    if (delivered) return;
    delivered = true;
    chrome.runtime.sendMessage({
      type: "FOORYS_E2I_GET_CLEARANCE",
      callbackUrl: callbackUrl,
      captchaId: captchaId,
      userAgent: navigator.userAgent
    }, (result) => {
      if (!result || !result.ok) {
        delivered = false;
        console.warn("Foorys E2i Helper:", result && result.error ? result.error : "brak odpowiedzi");
      }
    });
  }

  const timer = window.setInterval(() => {
    if (challengeVisible()) {
      challengeWasVisible = true;
      return;
    }
    // Wysyłamy sesję dopiero po zniknięciu ekranu weryfikacji.
    if (challengeWasVisible) {
      window.clearInterval(timer);
      window.setTimeout(deliver, 500);
    }
  }, 500);
})();
