"use strict";

const crypto = require("crypto");
const fs = require("fs");
const http = require("http");
const path = require("path");

const PORT = Number(process.env.PORT || 8080);
const DATA_DIR = process.env.DATA_DIR || "/data";
const STATE_FILE = path.join(DATA_DIR, "state.json");
const ADMIN_SECRET = String(process.env.FOORYS_RELAY_ADMIN_PASSWORD || process.env.FOORYS_RELAY_ADMIN_TOKEN || "");
const ACTIONS = {
  status: "Stan dekodera",
  diagnostics: "Pełna diagnostyka",
  network_diagnostic: "Diagnostyka sieci",
  speed_test: "Test prędkości internetu",
  console: "Konsola dekodera",
  refresh_catalog: "Odśwież katalog",
  install_foorys_channels: "Instaluj listę Foorys",
  install_bzyk83_hotbird: "Instaluj Bzyk83 Hotbird",
  install_bzyk83_dual: "Instaluj Bzyk83 Dual",
  install_channel: "Instaluj listę z katalogu",
  install_foorys_iptv: "Instaluj Foorys IPTV",
  install_picons_hotbird: "Picony Hotbird 13E",
  install_picons: "Instaluj picony z katalogu",
  install_plugin: "Instaluj plugin z katalogu",
  install_xstreamity: "Instaluj XStreamity",
  install_chocholousek: "Instaluj Chocholousek Picons",
  install_e2iplayer: "Instaluj E2iPlayer",
  install_oscam_stable: "Instaluj Oscam stable",
  install_oscam_emu: "Instaluj OSCam-emu",
  install_ncam: "Instaluj NCam",
  install_cccam: "Instaluj CCcam",
  oscam_dvbapi: "Aktualizuj oscam.dvbapi",
  update_plugin: "Aktualizuj E2-Foorys",
  restart_gui: "Restart GUI Enigma2",
  prepare_e2i_capture: "Przygotuj zdalną CAPTCHA E2iPlayer",
  deliver_e2i_capture: "Przekaż CAPTCHA E2iPlayer",
};
const CONSOLE_COMMANDS = {
  system: "Stan systemu",
  storage: "Pamięć i dysk",
  network: "Sieć",
  packages: "Pakiety E2iPlayer i softcam",
  processes: "Procesy dekodera",
};
const ALLOWED_ACTIONS = new Set(Object.keys(ACTIONS));
const ACTION_PARAMS = new Set(["install_channel", "install_picons", "install_plugin", "deliver_e2i_capture", "console"]);

if (ADMIN_SECRET.length < 8) throw new Error("Hasło administratora Relay musi mieć co najmniej 8 znaków.");
fs.mkdirSync(DATA_DIR, { recursive: true, mode: 0o700 });

function loadState() {
  try {
    const value = JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
    value.devices = value.devices || {};
    value.pairings = value.pairings || {};
    value.jobs = Array.isArray(value.jobs) ? value.jobs : [];
    value.captchaSessions = value.captchaSessions || {};
    value.browserSessions = value.browserSessions || {};
    value.captures = value.captures || {};
    return value;
  } catch (_error) {
    return { devices: {}, pairings: {}, jobs: [], captchaSessions: {}, browserSessions: {}, captures: {} };
  }
}
let state = loadState();
function saveState() {
  const temporary = STATE_FILE + ".tmp";
  fs.writeFileSync(temporary, JSON.stringify(state, null, 2), { mode: 0o600 });
  fs.renameSync(temporary, STATE_FILE);
}
function hash(value) { return crypto.createHash("sha256").update(String(value)).digest("hex"); }
function random(bytes) { return crypto.randomBytes(bytes).toString("base64url"); }
function newPairingCode() {
  let code;
  do { code = String(crypto.randomInt(1000, 10000)); } while (state.pairings[code]);
  return code;
}
function newCaptureCode() {
  let code;
  do { code = String(crypto.randomInt(100000, 1000000)); } while (state.captchaSessions[hash(code)]);
  return code;
}
function json(response, status, value, extraHeaders) {
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    ...(extraHeaders || {}),
  });
  response.end(JSON.stringify(value));
}
function readJson(request) {
  return new Promise((resolve, reject) => {
    let body = "";
    request.on("data", chunk => { body += chunk; if (body.length > 65536) request.destroy(); });
    request.on("end", () => { try { resolve(body ? JSON.parse(body) : {}); } catch (_error) { reject(new Error("Nieprawidłowy JSON.")); } });
    request.on("error", reject);
  });
}
function admin(request) {
  const authorization = String(request.headers.authorization || "");
  let candidate = authorization.replace(/^Bearer\s+/i, "");
  if (/^Basic\s+/i.test(authorization)) {
    try {
      const decoded = Buffer.from(authorization.replace(/^Basic\s+/i, ""), "base64").toString("utf8");
      const separator = decoded.indexOf(":");
      candidate = decoded.slice(0, separator) === "foorys" ? decoded.slice(separator + 1) : "";
    } catch (_error) { candidate = ""; }
  }
  return Boolean(candidate) && crypto.timingSafeEqual(Buffer.from(hash(candidate)), Buffer.from(hash(ADMIN_SECRET)));
}
function staticFile(response, filename, type) {
  response.writeHead(200, { "content-type": type, "cache-control": "no-store" });
  response.end(fs.readFileSync(path.join(__dirname, "web", filename)));
}
function device(request) {
  const token = String(request.headers["x-foorys-device-token"] || "");
  return Object.values(state.devices).find(item => item.tokenHash === hash(token));
}
function deviceName(value) {
  const name = String(value == null ? "" : value).trim();
  if (!name || name.length > 80 || /[\u0000-\u001f\u007f]/.test(name)) return null;
  return name;
}
function cleanup() {
  const now = Date.now();
  for (const [code, pairing] of Object.entries(state.pairings)) if (pairing.expiresAt < now) delete state.pairings[code];
  for (const [code, session] of Object.entries(state.captchaSessions)) if (session.expiresAt < now) delete state.captchaSessions[code];
  for (const [token, session] of Object.entries(state.browserSessions)) {
    if (session.expiresAt < now || (session.usedAt && session.usedAt < now - 120000)) delete state.browserSessions[token];
  }
  for (const [id, capture] of Object.entries(state.captures)) {
    if (capture.expiresAt < now || (capture.deliveredAt && capture.deliveredAt < now - 120000)) delete state.captures[id];
  }
  state.jobs = state.jobs.filter(job => job.createdAt > now - 7 * 86400000);
  for (const item of Object.values(state.devices)) {
    if (item.lastSeenAt && item.lastSeenAt < now - 120000) item.status = "offline";
  }
}
function jobParams(action, value) {
  if (!ACTION_PARAMS.has(action)) return {};
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  if (action === "deliver_e2i_capture") {
    const captureId = String(value.captureId || "").trim();
    return /^[A-Za-z0-9_-]{16,80}$/.test(captureId) ? { captureId } : null;
  }
  if (action === "console") {
    const command = String(value.command || "").trim();
    return Object.prototype.hasOwnProperty.call(CONSOLE_COMMANDS, command) ? { command } : null;
  }
  const id = String(value.id || "").trim();
  if (!/^[A-Za-z0-9._+-]{1,160}$/.test(id)) return null;
  return { id };
}

function privateHost(hostname) {
  const host = String(hostname || "").toLowerCase();
  if (host === "localhost" || host === "127.0.0.1" || host === "::1") return true;
  const parts = host.split(".").map(Number);
  return parts.length === 4 && parts.every(part => Number.isInteger(part) && part >= 0 && part <= 255) && (
    parts[0] === 10 ||
    (parts[0] === 192 && parts[1] === 168) ||
    (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31)
  );
}

function captureCallbackUrl(value) {
  try {
    const parsed = new URL(String(value || ""));
    if (parsed.protocol !== "http:" || !privateHost(parsed.hostname)) return null;
    return parsed.toString();
  } catch (_error) {
    return null;
  }
}

function captureBody(body) {
  const captureCode = String(body.captureCode || "").trim();
  const sessionToken = String(body.sessionToken || "").trim();
  let session;
  let codeKey = "";
  let browserKey = "";
  if (sessionToken) {
    if (!/^[A-Za-z0-9_-]{32,120}$/.test(sessionToken)) return { error: "Nieprawidłowy token sesji CAPTCHA." };
    browserKey = hash(sessionToken);
    session = state.browserSessions[browserKey];
    if (!session || session.expiresAt < Date.now()) return { error: "Sesja CAPTCHA wygasła lub jest nieprawidłowa." };
    if (session.usedAt) return { error: "Ta sesja CAPTCHA została już wykorzystana." };
  } else {
    if (!/^\d{6}$/.test(captureCode)) return { error: "Kod przechwycenia musi mieć 6 cyfr." };
    codeKey = hash(captureCode);
    session = state.captchaSessions[codeKey];
    if (!session || session.expiresAt < Date.now()) return { error: "Kod przechwycenia wygasł lub jest nieprawidłowy." };
  }
  const callbackUrl = captureCallbackUrl(body.callbackUrl);
  if (!callbackUrl) return { error: "Adres E2iPlayera musi być lokalnym adresem HTTP dekodera." };
  const captchaId = String(body.captchaId || "").trim();
  const token = String(body.token || "").trim();
  if (!captchaId || captchaId.length > 160 || /[\u0000-\u001f\u007f]/.test(captchaId)) return { error: "Nieprawidłowy identyfikator CAPTCHA." };
  if (!/^[A-Za-z0-9+/=_-]{16,60000}$/.test(token)) return { error: "Nieprawidłowa sesja CAPTCHA." };
  if (sessionToken && (callbackUrl !== session.callbackUrl || captchaId !== session.captchaId)) return { error: "Sesja CAPTCHA nie pasuje do aktywnego zadania dekodera." };
  const captureId = random(18);
  const now = Date.now();
  state.captures[captureId] = {
    deviceId: session.deviceId,
    callbackUrl,
    captchaId,
    token,
    createdAt: now,
    expiresAt: Math.min(session.expiresAt, now + 10 * 60000),
  };
  state.jobs.push({
    id: random(12),
    deviceId: session.deviceId,
    action: "deliver_e2i_capture",
    params: { captureId },
    createdAt: now,
    status: "pending",
  });
  if (codeKey) delete state.captchaSessions[codeKey];
  if (browserKey) {
    session.usedAt = now;
    if (session.captureCodeHash) delete state.captchaSessions[session.captureCodeHash];
  }
  saveState();
  return { captureId, deviceId: session.deviceId };
}

function browserSession(token) {
  const value = String(token || "").trim();
  if (!/^[A-Za-z0-9_-]{32,120}$/.test(value)) return null;
  return state.browserSessions[hash(value)] || null;
}

function queueBrowserPreparation(session) {
  if (session.jobId) return state.jobs.find(job => job.id === session.jobId) || null;
  const job = {
    id: random(12),
    deviceId: session.deviceId,
    action: "prepare_e2i_capture",
    params: {},
    createdAt: Date.now(),
    status: "pending",
    source: "captcha",
  };
  state.jobs.push(job);
  session.jobId = job.id;
  saveState();
  return job;
}

function browserTargetUrl(targetUrl, callbackUrl, captchaId, sessionToken) {
  let parsed;
  try { parsed = new URL(String(targetUrl || "")); } catch (_error) { return null; }
  if (!/^https?:$/.test(parsed.protocol) || !parsed.hostname) return null;
  const fragment = parsed.hash.replace(/^#/, "");
  if (!fragment.toLowerCase().startsWith("e2itcf")) return null;
  const extra = new URLSearchParams({ u: callbackUrl, c: captchaId, r: sessionToken }).toString();
  parsed.hash = fragment ? fragment + "&" + extra : extra;
  return parsed.toString();
}

function captchaBrowserPage(token) {
  const safeToken = JSON.stringify(String(token || "")).replace(/</g, "\\u003c");
  return `<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Foorys CAPTCHA</title>
<style>
  :root{color-scheme:dark}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#06111d;color:#edf7ff;font:16px Arial,sans-serif}
  main{width:min(620px,calc(100% - 36px));padding:30px;border:1px solid #246382;border-radius:16px;background:#0b2236;box-shadow:0 18px 60px #0008}
  h1{margin:0 0 12px;font-size:30px;color:#28d7f5}p{line-height:1.5;color:#c7dbe7}.state{margin-top:22px;padding:14px 16px;border-left:4px solid #55dfa4;background:#071927;color:#55dfa4;font-weight:bold}
  .small{font-size:13px;color:#8daabd;margin-top:18px}
</style></head><body><main><h1>Foorys CAPTCHA</h1>
<p>Sesja zdalna jest połączona z wybranym dekoderem. Gdy E2iPlayer będzie gotowy, strona weryfikacji otworzy się automatycznie.</p>
<div id="state" class="state">Łączę z dekoderem…</div><p class="small">Nie zamykaj tej karty. Weryfikację Cloudflare potwierdź ręcznie.</p>
<script>
const sessionToken=${safeToken};
const state=document.getElementById("state");
async function check(){
  try{
    const response=await fetch("/v1/captcha/browser/"+encodeURIComponent(sessionToken)+"/status",{cache:"no-store"});
    const data=await response.json();
    if(data.ready&&data.targetUrl){state.textContent="Otwieram stronę weryfikacji…";window.location.replace(data.targetUrl);return;}
    if(data.error){state.textContent=data.error;return;}
    state.textContent=data.status==="failed"?"Nie udało się przygotować sesji.":"Czekam na aktywną sesję MyE2i na dekoderze…";
  }catch(_error){state.textContent="Brak połączenia z Foorys Relay — ponawiam…";}
  window.setTimeout(check,2000);
}
check();
</script></main></body></html>`;
}

function captchaBrowserStatus(token) {
  const session = browserSession(token);
  if (!session || session.expiresAt < Date.now()) return { status: 404, value: { error: "Sesja CAPTCHA wygasła lub jest nieprawidłowa." } };
  const job = queueBrowserPreparation(session);
  if (!job) return { status: 500, value: { error: "Nie udało się utworzyć zadania CAPTCHA." } };
  if (job.status === "completed") {
    const data = job.data || {};
    const callbackUrl = captureCallbackUrl(data.callbackUrl);
    const captchaId = String(data.captchaId || "").trim();
    const targetUrl = browserTargetUrl(data.targetUrl, callbackUrl, captchaId, token);
    if (!callbackUrl || !captchaId || !targetUrl) return { status: 422, value: { error: "Dekoder zwrócił niekompletną sesję MyE2i." } };
    session.callbackUrl = callbackUrl;
    session.captchaId = captchaId;
    session.targetUrl = targetUrl;
    if (session.captureCodeHash && state.captchaSessions[session.captureCodeHash]) {
      state.captchaSessions[session.captureCodeHash].callbackUrl = callbackUrl;
      state.captchaSessions[session.captureCodeHash].captchaId = captchaId;
    }
    saveState();
    return { status: 200, value: { ready: true, targetUrl, expiresInSeconds: Math.max(0, Math.floor((session.expiresAt - Date.now()) / 1000)) } };
  }
  if (job.status === "failed") return { status: 200, value: { status: "failed", error: job.result || "Nie udało się przygotować sesji MyE2i." } };
  return { status: 200, value: { status: job.status, ready: false } };
}

function jobResultData(action, value) {
  if (action !== "prepare_e2i_capture") return null;
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const callbackUrl = captureCallbackUrl(value.callbackUrl);
  const captchaId = String(value.captchaId || "").trim();
  let targetUrl;
  try { targetUrl = new URL(String(value.targetUrl || "")); } catch (_error) { return null; }
  if (!callbackUrl || !captchaId || captchaId.length > 160 || /[\u0000-\u001f\u007f]/.test(captchaId)) return null;
  if (!/^https?:$/.test(targetUrl.protocol) || !targetUrl.hostname || !targetUrl.hash.toLowerCase().startsWith("#e2itcf")) return null;
  return { callbackUrl, captchaId, targetUrl: targetUrl.toString() };
}

const server = http.createServer(async (request, response) => {
  try {
    cleanup();
    const url = new URL(request.url, "http://relay.local");
    if (request.method === "GET" && url.pathname === "/") return staticFile(response, "index.html", "text/html; charset=utf-8");
    if (request.method === "GET" && url.pathname === "/app.js") return staticFile(response, "app.js", "application/javascript; charset=utf-8");
    if (request.method === "GET" && url.pathname === "/app.css") return staticFile(response, "app.css", "text/css; charset=utf-8");
    if (request.method === "GET" && url.pathname === "/health") return json(response, 200, { ok: true });
    const browserPath = url.pathname.match(/^\/e2i\/([A-Za-z0-9_-]{32,120})\/?$/);
    if (request.method === "GET" && browserPath) {
      if (!browserSession(browserPath[1])) return json(response, 404, { error: "Sesja CAPTCHA wygasła lub jest nieprawidłowa." });
      response.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" });
      return response.end(captchaBrowserPage(browserPath[1]));
    }
    const browserStatusPath = url.pathname.match(/^\/v1\/captcha\/browser\/([A-Za-z0-9_-]{32,120})\/status\/?$/);
    if (request.method === "GET" && browserStatusPath) {
      const result = captchaBrowserStatus(browserStatusPath[1]);
      return json(response, result.status, result.value);
    }
    if (request.method === "OPTIONS" && url.pathname === "/v1/captcha/submit") {
      response.writeHead(204, {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "POST, OPTIONS",
        "access-control-allow-headers": "content-type",
        "cache-control": "no-store",
      });
      return response.end();
    }
    if (request.method === "POST" && url.pathname === "/v1/captcha/submit") {
      const body = await readJson(request);
      const result = captureBody(body);
      if (result.error) return json(response, 401, result, { "access-control-allow-origin": "*" });
      return json(response, 201, { ok: true }, { "access-control-allow-origin": "*" });
    }
    if (url.pathname.startsWith("/v1/admin/")) {
      if (!admin(request)) return json(response, 401, { error: "Brak autoryzacji administratora." });
      if (request.method === "GET" && url.pathname === "/v1/admin/devices") return json(response, 200, { devices: Object.values(state.devices).map(({ tokenHash, ...item }) => item) });
      const devicePath = url.pathname.match(/^\/v1\/admin\/devices\/([A-Za-z0-9_-]{8,80})$/);
      if (request.method === "DELETE" && devicePath) {
        const deviceId = devicePath[1];
        const current = state.devices[deviceId];
        if (!current) return json(response, 404, { error: "Nie znaleziono dekodera." });
        if (current.status === "online") return json(response, 409, { error: "Aktywny dekoder jest chroniony. Usuń go dopiero po rozłączeniu." });
        delete state.devices[deviceId];
        state.jobs = state.jobs.filter(job => job.deviceId !== deviceId);
        for (const [code, session] of Object.entries(state.captchaSessions)) if (session.deviceId === deviceId) delete state.captchaSessions[code];
        for (const [token, session] of Object.entries(state.browserSessions)) if (session.deviceId === deviceId) delete state.browserSessions[token];
        for (const [id, capture] of Object.entries(state.captures)) if (capture.deviceId === deviceId) delete state.captures[id];
        saveState();
        return json(response, 200, { ok: true, deviceId });
      }
      if (request.method === "PATCH" && devicePath) {
        const deviceId = devicePath[1];
        const current = state.devices[deviceId];
        if (!current) return json(response, 404, { error: "Nie znaleziono dekodera." });
        const body = await readJson(request);
        const name = deviceName(body.name);
        if (!name) return json(response, 400, { error: "Nazwa musi mieć od 1 do 80 znaków i nie może zawierać znaków sterujących." });
        current.name = name;
        saveState();
        const { tokenHash, ...safeDevice } = current;
        return json(response, 200, { device: safeDevice });
      }
      if (request.method === "GET" && url.pathname === "/v1/admin/actions") return json(response, 200, { actions: ACTIONS });
      if (request.method === "GET" && url.pathname === "/v1/admin/jobs") {
        const deviceId = String(url.searchParams.get("deviceId") || "");
        const jobs = state.jobs.filter(job => !deviceId || job.deviceId === deviceId).slice(-100).reverse();
        return json(response, 200, { jobs });
      }
      if (request.method === "POST" && url.pathname === "/v1/admin/pairings") {
        const code = newPairingCode(); state.pairings[code] = { expiresAt: Date.now() + 15 * 60000 }; saveState();
        return json(response, 201, { pairingCode: code, expiresInSeconds: 900 });
      }
      if (request.method === "POST" && url.pathname === "/v1/admin/captcha/sessions") {
        const body = await readJson(request);
        const deviceId = String(body.deviceId || "");
        if (!state.devices[deviceId]) return json(response, 400, { error: "Nie znaleziono dekodera." });
        const captureCode = newCaptureCode();
        state.captchaSessions[hash(captureCode)] = {
          deviceId,
          createdAt: Date.now(),
          expiresAt: Date.now() + 10 * 60000,
        };
        const browserToken = random(32);
        const browserKey = hash(browserToken);
        state.captchaSessions[hash(captureCode)].browserSessionHash = browserKey;
        state.browserSessions[browserKey] = {
          id: random(12),
          deviceId,
          captureCodeHash: hash(captureCode),
          createdAt: Date.now(),
          expiresAt: Date.now() + 10 * 60000,
        };
        saveState();
        return json(response, 201, { captureCode, browserPath: "/e2i/" + browserToken, expiresInSeconds: 600 });
      }
      if (request.method === "POST" && url.pathname === "/v1/admin/jobs") {
        const body = await readJson(request);
        const action = String(body.action || "");
        const params = jobParams(action, body.params);
        if (!state.devices[body.deviceId] || !ALLOWED_ACTIONS.has(action) || params === null) return json(response, 400, { error: "Nieprawidłowy dekoder, akcja lub parametr." });
        const job = { id: random(12), deviceId: body.deviceId, action, params, createdAt: Date.now(), status: "pending" };
        state.jobs.push(job); saveState(); return json(response, 201, { job });
      }
      return json(response, 404, { error: "Nie znaleziono." });
    }
    if (request.method === "POST" && url.pathname === "/v1/device/register") {
      const body = await readJson(request); const pairing = state.pairings[String(body.pairingCode || "")];
      if (!pairing || pairing.expiresAt < Date.now()) return json(response, 401, { error: "Kod parowania wygasł." });
      const id = random(10), token = random(32);
      state.devices[id] = { id, name: deviceName(body.name) || "Dekoder", tokenHash: hash(token), pairedAt: Date.now(), lastSeenAt: null, status: "offline" };
      delete state.pairings[body.pairingCode]; saveState(); return json(response, 201, { deviceId: id, deviceToken: token });
    }
    const current = device(request);
    if (!current) return json(response, 401, { error: "Brak autoryzacji dekodera." });
    if (request.method === "POST" && url.pathname === "/v1/device/heartbeat") {
      const body = await readJson(request); current.lastSeenAt = Date.now(); current.status = "online"; current.metrics = body.metrics || {}; saveState(); return json(response, 200, { ok: true });
    }
    if (request.method === "GET" && url.pathname === "/v1/device/jobs") {
      const now = Date.now();
      const candidates = state.jobs.filter(job => job.deviceId === current.id && (job.status === "pending" || (job.status === "delivered" && (job.deliveredAt || 0) < now - 120000))).slice(0, 3);
      const jobs = [];
      candidates.forEach(job => {
        if (job.action === "deliver_e2i_capture") {
          const capture = state.captures[job.params && job.params.captureId];
          if (!capture || capture.expiresAt < now) {
            job.status = "failed";
            job.result = "Sesja CAPTCHA wygasła przed odebraniem przez dekoder.";
            job.finishedAt = now;
            return;
          }
          capture.deliveredAt = now;
          jobs.push({ ...job, capture: { callbackUrl: capture.callbackUrl, captchaId: capture.captchaId, token: capture.token } });
          job.status = "delivered";
          job.deliveredAt = now;
          return;
        }
        job.status = "delivered";
        job.deliveredAt = now;
        jobs.push(job);
      });
      saveState(); return json(response, 200, { jobs });
    }
    if (request.method === "POST" && /^\/v1\/device\/jobs\/[^/]+\/result$/.test(url.pathname)) {
      const job = state.jobs.find(item => item.id === url.pathname.split("/")[4] && item.deviceId === current.id);
      if (!job) return json(response, 404, { error: "Nie znaleziono zadania." });
      const body = await readJson(request);
      if (body.ok && job.action === "prepare_e2i_capture") {
        const data = jobResultData(job.action, body.data);
        if (!data) return json(response, 400, { error: "Nieprawidłowe dane przygotowanej sesji CAPTCHA." });
        job.data = data;
      }
      job.status = body.ok ? "completed" : "failed"; job.result = String(body.message || "").slice(0, 1800); job.finishedAt = Date.now();
      if (job.action === "deliver_e2i_capture" && job.params && job.params.captureId) delete state.captures[job.params.captureId];
      saveState(); return json(response, 200, { ok: true });
    }
    return json(response, 404, { error: "Nie znaleziono." });
  } catch (error) { return json(response, 500, { error: "Błąd Relay." }); }
});
server.listen(PORT, "0.0.0.0", () => console.log("Foorys Relay nasłuchuje na porcie " + PORT));
