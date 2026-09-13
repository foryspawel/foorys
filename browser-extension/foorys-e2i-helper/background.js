const DEFAULT_DECODER = "192.168.18.177:9001";

function isPrivateHost(hostname) {
  const host = String(hostname || "").toLowerCase();
  if (host === "localhost" || host === "127.0.0.1" || host === "::1") return true;
  const parts = host.split(".").map(Number);
  return parts.length === 4 && (
    parts[0] === 10 ||
    (parts[0] === 192 && parts[1] === 168) ||
    (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31)
  );
}

function privateCallback(callbackUrl) {
  try {
    const url = new URL(callbackUrl);
    return url.protocol === "http:" && isPrivateHost(url.hostname);
  } catch (_error) {
    return false;
  }
}

function callbackEndpoint(callbackUrl, captchaId, token) {
  const endpoint = new URL(callbackUrl);
  endpoint.pathname = endpoint.pathname.replace(/\/?$/, "/") + "response";
  endpoint.search = "";
  endpoint.searchParams.set("c", captchaId);
  endpoint.searchParams.set("token", token);
  return endpoint.toString();
}

chrome.runtime.onInstalled.addListener(async () => {
  const stored = await chrome.storage.local.get("decoderAddress");
  if (!stored.decoderAddress) {
    await chrome.storage.local.set({ decoderAddress: DEFAULT_DECODER });
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "FOORYS_E2I_GET_CLEARANCE") return;
  const tabUrl = sender.tab && sender.tab.url;
  if (!tabUrl || !privateCallback(message.callbackUrl)) {
    sendResponse({ ok: false, error: "Niedozwolony adres zwrotny." });
    return;
  }
  chrome.cookies.getAll({ url: tabUrl }, (cookies) => {
    const clearance = (cookies || []).filter((cookie) => cookie.name === "cf_clearance");
    if (!clearance.length) {
      sendResponse({ ok: false, error: "Nie znaleziono cookie cf_clearance. Ukończ weryfikację w tej karcie." });
      return;
    }
    const payload = {
      user_agent: sender.tab && sender.tab.userAgent ? sender.tab.userAgent : "",
      cookie: clearance,
      url: tabUrl,
      domain: "." + new URL(tabUrl).hostname
    };
    // navigator.userAgent is przekazywany przez content script w message.userAgent.
    payload.user_agent = message.userAgent || payload.user_agent;
    const token = btoa(unescape(encodeURIComponent(JSON.stringify(payload))));
    fetch(callbackEndpoint(message.callbackUrl, message.captchaId, token))
      .then((response) => {
        if (!response.ok) throw new Error("HTTP " + response.status);
        sendResponse({ ok: true });
      })
      .catch((error) => sendResponse({ ok: false, error: String(error.message || error) }));
  });
  return true;
});
