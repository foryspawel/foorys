(function () {
  "use strict";

  const isLocalE2iPage = /\/e2it\.html\/?$/i.test(location.pathname);
  if (isLocalE2iPage) {
    chrome.runtime.sendMessage({
      type: "FOORYS_E2I_REGISTER_LOCAL_PAGE",
      callbackUrl: location.origin + "/"
    });
    return;
  }

  if (!location.hash.toLowerCase().startsWith("#e2itcf")) return;

  function hashParams() {
    const fragment = location.hash.slice(1);
    const separator = fragment.indexOf("_sep_");
    const query = separator >= 0 ? fragment.slice(separator + 5) : fragment;
    return new URLSearchParams(query);
  }

  const params = hashParams();
  const callbackUrl = params.get("u") || "";
  const captchaId = params.get("c") || "";
  const relaySessionToken = params.get("r") || "";
  if (!captchaId) return;

  let challengeWasVisible = false;
  let stableWithoutChallenge = 0;
  let delivered = false;

  function challengeVisible() {
    const form = document.querySelector("#challenge-form");
    if (form && form.getClientRects().length) return true;
    if (document.querySelector("iframe[src*='challenges.cloudflare.com'], [id*='cf-chl'], [class*='cf-chl']")) return true;
    const links = Array.from(document.querySelectorAll("link[href],script"));
    if (links.some((element) => String(element.href || element.textContent || "").includes("/challenges"))) return true;
    return /verify you are human|checking your browser|just a moment|turnstile/i.test(document.body && document.body.innerText || "");
  }

  function deliver() {
    if (delivered) return;
    delivered = true;
    chrome.runtime.sendMessage({
      type: "FOORYS_E2I_GET_CLEARANCE",
      callbackUrl: callbackUrl,
      captchaId: captchaId,
      relaySessionToken: relaySessionToken,
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
      stableWithoutChallenge = 0;
      return;
    }
    stableWithoutChallenge += 1;
    // Po rozwiązaniu lub po chwili od wejścia na stronę przekazujemy cookie.
    // Sama weryfikacja nadal wymaga ręcznego działania użytkownika.
    if (challengeWasVisible || stableWithoutChallenge >= 10) {
      window.clearInterval(timer);
      window.setTimeout(deliver, 500);
    }
  }, 500);
})();
