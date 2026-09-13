const DEFAULT_DECODER = "192.168.18.177:9001";
const DEFAULT_RELAY = "https://raport.forys.pro:9443";

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

function relayEndpoint(relayUrl) {
  const endpoint = new URL(relayUrl);
  endpoint.pathname = endpoint.pathname.replace(/\/?$/, "/") + "v1/captcha/submit";
  endpoint.search = "";
  return endpoint.toString();
}

function validRelayUrl(relayUrl) {
  try {
    const endpoint = new URL(relayUrl);
    if (endpoint.protocol === "https:") return true;
    return endpoint.protocol === "http:" && isPrivateHost(endpoint.hostname);
  } catch (_error) {
    return false;
  }
}

chrome.runtime.onInstalled.addListener(async () => {
  const stored = await chrome.storage.local.get(["decoderAddress", "relayUrl"]);
  const defaults = {};
  if (!stored.decoderAddress) defaults.decoderAddress = DEFAULT_DECODER;
  if (!stored.relayUrl) defaults.relayUrl = DEFAULT_RELAY;
  if (Object.keys(defaults).length) await chrome.storage.local.set(defaults);
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
    chrome.storage.local.get(["relayUrl", "relayCaptureCode"]).then((stored) => {
      const captureCode = String(stored.relayCaptureCode || "").trim();
      const relayUrl = String(stored.relayUrl || DEFAULT_RELAY).trim().replace(/\/$/, "");
      const endpoint = captureCode && validRelayUrl(relayUrl)
        ? relayEndpoint(relayUrl)
        : callbackEndpoint(message.callbackUrl, message.captchaId, token);
      const body = captureCode && validRelayUrl(relayUrl)
        ? JSON.stringify({
          captureCode: captureCode,
          callbackUrl: message.callbackUrl,
          captchaId: message.captchaId,
          token: token
        })
        : null;
      return fetch(endpoint, body ? {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body
      } : {})
        .then((response) => response.json().catch(() => ({})).then((data) => {
          if (!response.ok) throw new Error(data.error || ("HTTP " + response.status));
          return data;
        }))
        .then(() => {
          if (body) return chrome.storage.local.remove("relayCaptureCode");
          return null;
        });
    })
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error.message || error) }));
  });
  return true;
});
