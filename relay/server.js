"use strict";

const crypto = require("crypto");
const fs = require("fs");
const http = require("http");
const path = require("path");

const PORT = Number(process.env.PORT || 8080);
const DATA_DIR = process.env.DATA_DIR || "/data";
const STATE_FILE = path.join(DATA_DIR, "state.json");
const ADMIN_TOKEN = String(process.env.FOORYS_RELAY_ADMIN_TOKEN || "");
const ALLOWED_ACTIONS = new Set(["status", "refresh_catalog", "diagnostics", "update_plugin"]);

if (ADMIN_TOKEN.length < 32) throw new Error("FOORYS_RELAY_ADMIN_TOKEN musi mieć co najmniej 32 znaki.");
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
  const token = String(request.headers.authorization || "").replace(/^Bearer\s+/i, "");
  return token && crypto.timingSafeEqual(Buffer.from(hash(token)), Buffer.from(hash(ADMIN_TOKEN)));
}
function device(request) {
  const token = String(request.headers["x-foorys-device-token"] || "");
  return Object.values(state.devices).find(item => item.tokenHash === hash(token));
}
function cleanup() {
  const now = Date.now();
  for (const [code, pairing] of Object.entries(state.pairings)) if (pairing.expiresAt < now) delete state.pairings[code];
  state.jobs = state.jobs.filter(job => job.createdAt > now - 7 * 86400000);
}

const server = http.createServer(async (request, response) => {
  try {
    cleanup();
    const url = new URL(request.url, "http://relay.local");
    if (request.method === "GET" && url.pathname === "/health") return json(response, 200, { ok: true });
    if (url.pathname.startsWith("/v1/admin/")) {
      if (!admin(request)) return json(response, 401, { error: "Brak autoryzacji administratora." });
      if (request.method === "GET" && url.pathname === "/v1/admin/devices") return json(response, 200, { devices: Object.values(state.devices).map(({ tokenHash, ...item }) => item) });
      if (request.method === "POST" && url.pathname === "/v1/admin/pairings") {
        const code = random(18); state.pairings[code] = { expiresAt: Date.now() + 15 * 60000 }; saveState();
        return json(response, 201, { pairingCode: code, expiresInSeconds: 900 });
      }
      if (request.method === "POST" && url.pathname === "/v1/admin/jobs") {
        const body = await readJson(request);
        if (!state.devices[body.deviceId] || !ALLOWED_ACTIONS.has(body.action)) return json(response, 400, { error: "Nieprawidłowy dekoder lub akcja." });
        const job = { id: random(12), deviceId: body.deviceId, action: body.action, createdAt: Date.now(), status: "pending" };
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
      const jobs = state.jobs.filter(job => job.deviceId === current.id && job.status === "pending");
      jobs.forEach(job => { job.status = "delivered"; }); saveState(); return json(response, 200, { jobs });
    }
    if (request.method === "POST" && /^\/v1\/device\/jobs\/[^/]+\/result$/.test(url.pathname)) {
      const job = state.jobs.find(item => item.id === url.pathname.split("/")[4] && item.deviceId === current.id);
      if (!job) return json(response, 404, { error: "Nie znaleziono zadania." });
      const body = await readJson(request); job.status = body.ok ? "completed" : "failed"; job.result = String(body.message || "").slice(0, 1000); saveState(); return json(response, 200, { ok: true });
    }
    return json(response, 404, { error: "Nie znaleziono." });
  } catch (error) { return json(response, 500, { error: "Błąd Relay." }); }
});
server.listen(PORT, "0.0.0.0", () => console.log("Foorys Relay nasłuchuje na porcie " + PORT));
