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
};
const ALLOWED_ACTIONS = new Set(Object.keys(ACTIONS));
const ACTION_PARAMS = new Set(["install_channel", "install_picons", "install_plugin"]);

if (ADMIN_SECRET.length < 8) throw new Error("Hasło administratora Relay musi mieć co najmniej 8 znaków.");
fs.mkdirSync(DATA_DIR, { recursive: true, mode: 0o700 });

function loadState() {
  try { return JSON.parse(fs.readFileSync(STATE_FILE, "utf8")); }
  catch (_error) { return { devices: {}, pairings: {}, jobs: [] }; }
}
let state = loadState();
function saveState() {
  const temporary = STATE_FILE + ".tmp";
  fs.writeFileSync(temporary, JSON.stringify(state, null, 2), { mode: 0o600 });
  fs.renameSync(temporary, STATE_FILE);
}
function hash(value) { return crypto.createHash("sha256").update(String(value)).digest("hex"); }
function random(bytes) { return crypto.randomBytes(bytes).toString("base64url"); }
function json(response, status, value) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
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
function cleanup() {
  const now = Date.now();
  for (const [code, pairing] of Object.entries(state.pairings)) if (pairing.expiresAt < now) delete state.pairings[code];
  state.jobs = state.jobs.filter(job => job.createdAt > now - 7 * 86400000);
  for (const item of Object.values(state.devices)) {
    if (item.lastSeenAt && item.lastSeenAt < now - 120000) item.status = "offline";
  }
}
function jobParams(action, value) {
  if (!ACTION_PARAMS.has(action)) return {};
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const id = String(value.id || "").trim();
  if (!/^[A-Za-z0-9._+-]{1,160}$/.test(id)) return null;
  return { id };
}

const server = http.createServer(async (request, response) => {
  try {
    cleanup();
    const url = new URL(request.url, "http://relay.local");
    if (request.method === "GET" && url.pathname === "/") return staticFile(response, "index.html", "text/html; charset=utf-8");
    if (request.method === "GET" && url.pathname === "/app.js") return staticFile(response, "app.js", "application/javascript; charset=utf-8");
    if (request.method === "GET" && url.pathname === "/app.css") return staticFile(response, "app.css", "text/css; charset=utf-8");
    if (request.method === "GET" && url.pathname === "/health") return json(response, 200, { ok: true });
    if (url.pathname.startsWith("/v1/admin/")) {
      if (!admin(request)) return json(response, 401, { error: "Brak autoryzacji administratora." });
      if (request.method === "GET" && url.pathname === "/v1/admin/devices") return json(response, 200, { devices: Object.values(state.devices).map(({ tokenHash, ...item }) => item) });
      if (request.method === "GET" && url.pathname === "/v1/admin/actions") return json(response, 200, { actions: ACTIONS });
      if (request.method === "GET" && url.pathname === "/v1/admin/jobs") {
        const deviceId = String(url.searchParams.get("deviceId") || "");
        const jobs = state.jobs.filter(job => !deviceId || job.deviceId === deviceId).slice(-100).reverse();
        return json(response, 200, { jobs });
      }
      if (request.method === "POST" && url.pathname === "/v1/admin/pairings") {
        const code = random(18); state.pairings[code] = { expiresAt: Date.now() + 15 * 60000 }; saveState();
        return json(response, 201, { pairingCode: code, expiresInSeconds: 900 });
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
      state.devices[id] = { id, name: String(body.name || "Dekoder").slice(0, 80), tokenHash: hash(token), pairedAt: Date.now(), lastSeenAt: null, status: "offline" };
      delete state.pairings[body.pairingCode]; saveState(); return json(response, 201, { deviceId: id, deviceToken: token });
    }
    const current = device(request);
    if (!current) return json(response, 401, { error: "Brak autoryzacji dekodera." });
    if (request.method === "POST" && url.pathname === "/v1/device/heartbeat") {
      const body = await readJson(request); current.lastSeenAt = Date.now(); current.status = "online"; current.metrics = body.metrics || {}; saveState(); return json(response, 200, { ok: true });
    }
    if (request.method === "GET" && url.pathname === "/v1/device/jobs") {
      const now = Date.now();
      const jobs = state.jobs.filter(job => job.deviceId === current.id && (job.status === "pending" || (job.status === "delivered" && (job.deliveredAt || 0) < now - 120000))).slice(0, 3);
      jobs.forEach(job => { job.status = "delivered"; job.deliveredAt = now; }); saveState(); return json(response, 200, { jobs });
    }
    if (request.method === "POST" && /^\/v1\/device\/jobs\/[^/]+\/result$/.test(url.pathname)) {
      const job = state.jobs.find(item => item.id === url.pathname.split("/")[4] && item.deviceId === current.id);
      if (!job) return json(response, 404, { error: "Nie znaleziono zadania." });
      const body = await readJson(request); job.status = body.ok ? "completed" : "failed"; job.result = String(body.message || "").slice(0, 1800); job.finishedAt = Date.now(); saveState(); return json(response, 200, { ok: true });
    }
    return json(response, 404, { error: "Nie znaleziono." });
  } catch (error) { return json(response, 500, { error: "Błąd Relay." }); }
});
server.listen(PORT, "0.0.0.0", () => console.log("Foorys Relay nasłuchuje na porcie " + PORT));
