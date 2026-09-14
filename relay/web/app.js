const $ = selector => document.querySelector(selector);
let password = sessionStorage.getItem("foorysRelayPassword") || "";

const BUTTONS = [
  ["status", "Stan"],
  ["diagnostics", "Diagnostyka"],
  ["network_diagnostic", "Sieć"],
  ["speed_test", "Prędkość"],
  ["refresh_catalog", "Katalog"],
  ["install_foorys_channels", "Lista Foorys"],
  ["install_bzyk83_hotbird", "Bzyk83 HB"],
  ["install_bzyk83_dual", "Bzyk83 Dual"],
  ["install_foorys_iptv", "Foorys IPTV"],
  ["install_picons_hotbird", "Picony HB"],
  ["install_xstreamity", "XStreamity"],
  ["install_chocholousek", "Chocholousek"],
  ["install_e2iplayer", "E2iPlayer"],
  ["install_oscam_stable", "Oscam stable"],
  ["install_oscam_emu", "OSCam-emu"],
  ["install_ncam", "NCam"],
  ["install_cccam", "CCcam"],
  ["oscam_dvbapi", "oscam.dvbapi"],
  ["update_plugin", "Aktualizuj Foorys"],
  ["restart_gui", "Restart GUI"],
];
const CAPTCHA_BUTTON = "Otwórz CAPTCHA zdalnie";
const CONSOLE_COMMANDS = [
  ["system", "Stan systemu"],
  ["storage", "Pamięć i dysk"],
  ["network", "Sieć"],
  ["packages", "Pakiety"],
  ["processes", "Procesy"],
];
let openConsoleDeviceId = "";

function headers() {
  return { Authorization: "Basic " + btoa("foorys:" + password), "Content-Type": "application/json" };
}

async function request(url, options = {}) {
  const response = await fetch(url, { ...options, headers: { ...headers(), ...(options.headers || {}) } });
  let data = {};
  try { data = await response.json(); } catch (_error) { data = {}; }
  if (!response.ok) throw new Error(data.error || "Błąd połączenia");
  return data;
}

function esc(value) {
  const element = document.createElement("span");
  element.textContent = value == null ? "" : String(value);
  return element.innerHTML;
}

function actionLabel(action) {
  if (action === "console") return "Konsola dekodera";
  const found = BUTTONS.find(item => item[0] === action);
  return found ? found[1] : action;
}

function jobLabel(job) {
  if (job.action !== "console") return actionLabel(job.action);
  const command = job.params && job.params.command;
  const found = CONSOLE_COMMANDS.find(item => item[0] === command);
  return `Konsola: ${found ? found[1] : "polecenie"}`;
}

function formatSize(value) {
  if (value == null || Number.isNaN(Number(value))) return "n/d";
  let number = Number(value);
  const units = ["B", "KB", "MB", "GB", "TB"];
  let index = 0;
  while (number >= 1024 && index < units.length - 1) { number /= 1024; index += 1; }
  return `${number.toFixed(index ? 1 : 0)} ${units[index]}`;
}

function metricsText(device) {
  const metrics = device.metrics || {};
  const memory = metrics.memory || {};
  const flash = metrics.flash || {};
  return `CPU ${metrics.cpu_percent == null ? "n/d" : metrics.cpu_percent + "%"} · RAM ${memory.percent == null ? "n/d" : memory.percent + "%"} · RootFS wolne ${formatSize(flash.free)}`;
}

function jobHistory(deviceId, jobs) {
  const own = jobs.filter(job => job.deviceId === deviceId).slice(0, 5);
  if (!own.length) return "<small>Brak zadań.</small>";
  return `<div class="history"><b>Ostatnie zadania</b>${own.map(job => `<div><span>${esc(jobLabel(job))}</span><span class="${job.status === "completed" ? "ok" : job.status === "failed" ? "bad" : "wait"}">${esc(job.status)}</span>${job.result ? `<small>${esc(job.result)}</small>` : ""}</div>`).join("")}</div>`;
}

function consolePanel(device, jobs) {
  if (openConsoleDeviceId !== device.id) return "";
  const consoleJobs = jobs.filter(job => job.deviceId === device.id && job.action === "console").slice(0, 3);
  const output = consoleJobs.length ? consoleJobs.map(job => `<div class="console-result"><b>${esc(jobLabel(job))}</b><span class="${job.status === "completed" ? "ok" : job.status === "failed" ? "bad" : "wait"}">${esc(job.status)}</span>${job.result ? `<pre>${esc(job.result)}</pre>` : ""}</div>`).join("") : "<small>Wybierz polecenie; wynik pojawi się tutaj po odebraniu go przez dekoder.</small>";
  const buttons = CONSOLE_COMMANDS.map(([command, label]) => `<button type="button" class="console-button" data-console-command="${esc(command)}" data-device="${esc(device.id)}">${esc(label)}</button>`).join("");
  return `<div class="console"><div class="console-title"><b>Konsola sterowania</b><span>Tylko bezpieczne polecenia dla sparowanego dekodera</span></div><div class="console-buttons">${buttons}</div><div class="console-output">${output}</div></div>`;
}

function deviceCard(device, jobs) {
  const online = device.status === "online";
  const name = device.name || "Dekoder";
  const buttons = BUTTONS.map(([action, label]) => `<button class="action-button ${action === "restart_gui" ? "danger" : ""}" data-device="${esc(device.id)}" data-action="${action}">${esc(label)}</button>`).join("");
  const removeButton = online ? "" : `<button type="button" class="action-button danger delete-button" data-device="${esc(device.id)}" data-delete="1">Usuń nieaktywny</button>`;
  return `<article><header><div class="device-name"><div class="device-name-row"><h2>${esc(name)}</h2><button type="button" class="rename-button" data-device="${esc(device.id)}" data-rename="1">Zmień nazwę</button></div><small>ID: ${esc(device.id)}</small></div><span class="${online ? "online" : "offline"}">${online ? "online" : "offline"}</span></header><p class="metrics">${esc(metricsText(device))}</p><p class="last-seen">Ostatni kontakt: ${device.lastSeenAt ? esc(new Date(device.lastSeenAt).toLocaleString()) : "brak"}</p><div class="device-actions"><button type="button" class="action-button console-toggle" data-device="${esc(device.id)}" data-console="1">Konsola</button><button class="action-button capture-button" data-device="${esc(device.id)}" data-captcha="1">${CAPTCHA_BUTTON}</button>${buttons}${removeButton}</div>${consolePanel(device, jobs)}${jobHistory(device.id, jobs)}</article>`;
}

async function load() {
  try {
    const [devicesData, jobsData] = await Promise.all([request("/v1/admin/devices"), request("/v1/admin/jobs")]);
    const devices = devicesData.devices || [];
    const jobs = jobsData.jobs || [];
    $("#devices").innerHTML = devices.length ? devices.map(device => deviceCard(device, jobs)).join("") : "<p>Nie ma jeszcze sparowanych dekoderów.</p>";
    $("#notice").textContent = `Dekodery: ${devices.length} · odświeżono ${new Date().toLocaleTimeString()}`;
  } catch (error) { $("#notice").textContent = error.message; }
}

async function login() {
  password = $("#password").value;
  try {
    await request("/v1/admin/devices");
    sessionStorage.setItem("foorysRelayPassword", password);
    $("#login").hidden = true;
    $("#dashboard").hidden = false;
    load();
  } catch (_error) { $("#login-error").textContent = "Nieprawidłowe hasło."; }
}

async function queueAction(deviceId, action) {
  const warning = action === "restart_gui" ? "Restart GUI przerwie chwilowo obraz na dekoderze. Kontynuować?" : `Wysłać akcję „${actionLabel(action)}” do dekodera?`;
  if (!window.confirm(warning)) return;
  try {
    await request("/v1/admin/jobs", { method: "POST", body: JSON.stringify({ deviceId, action }) });
    $("#notice").textContent = `Zadanie „${actionLabel(action)}” dodane do kolejki.`;
    await load();
  } catch (error) { $("#notice").textContent = error.message; }
}

async function queueConsole(deviceId, command) {
  const found = CONSOLE_COMMANDS.find(item => item[0] === command);
  const label = found ? found[1] : "polecenie";
  try {
    await request("/v1/admin/jobs", { method: "POST", body: JSON.stringify({ deviceId, action: "console", params: { command } }) });
    $("#notice").textContent = `Konsola: „${label}” dodana do kolejki.`;
    await load();
  } catch (error) { $("#notice").textContent = error.message; }
}

async function startCaptchaSession(deviceId) {
  try {
    const data = await request("/v1/admin/captcha/sessions", { method: "POST", body: JSON.stringify({ deviceId }) });
    const code = data.captureCode || "";
    const browserUrl = data.browserPath ? new URL(data.browserPath, window.location.origin).toString() : "";
    if (navigator.clipboard && browserUrl) navigator.clipboard.writeText(browserUrl).catch(() => {});
    const link = browserUrl ? `<a href="${esc(browserUrl)}" target="_blank" rel="noopener">Otwórz sesję w Chrome</a>` : "";
    $("#notice").innerHTML = `Sesja CAPTCHA gotowa · ważna 10 min. ${link} · adres został skopiowany. Kod awaryjny: <b>${esc(code)}</b>`;
  } catch (error) { $("#notice").textContent = error.message; }
}

async function renameDevice(deviceId, currentName) {
  const value = window.prompt("Podaj nazwę dekodera:", currentName || "Dekoder");
  if (value === null) return;
  const name = value.trim();
  if (!name) { $("#notice").textContent = "Nazwa dekodera nie może być pusta."; return; }
  if (name.length > 80) { $("#notice").textContent = "Nazwa dekodera może mieć maksymalnie 80 znaków."; return; }
  try {
    await request(`/v1/admin/devices/${encodeURIComponent(deviceId)}`, { method: "PATCH", body: JSON.stringify({ name }) });
    $("#notice").textContent = `Zapisano nazwę „${name}”.`;
    await load();
  } catch (error) { $("#notice").textContent = error.message; }
}

async function deleteDevice(deviceId, currentName) {
  if (!window.confirm(`Usunąć nieaktywny dekoder „${currentName || "Dekoder"}” wraz z jego zadaniami?`)) return;
  try {
    await request(`/v1/admin/devices/${encodeURIComponent(deviceId)}`, { method: "DELETE" });
    $("#notice").textContent = `Usunięto dekoder „${currentName || "Dekoder"}”.`;
    await load();
  } catch (error) { $("#notice").textContent = error.message; }
}

$("#sign-in").onclick = login;
$("#password").onkeydown = event => { if (event.key === "Enter") login(); };
$("#refresh").onclick = load;
$("#sign-out").onclick = () => { sessionStorage.removeItem("foorysRelayPassword"); location.reload(); };
$("#devices").onclick = event => {
  const consoleToggle = event.target.closest("button[data-console]");
  if (consoleToggle) {
    openConsoleDeviceId = openConsoleDeviceId === consoleToggle.dataset.device ? "" : consoleToggle.dataset.device;
    load();
    return;
  }
  const consoleCommand = event.target.closest("button[data-console-command]");
  if (consoleCommand) {
    queueConsole(consoleCommand.dataset.device, consoleCommand.dataset.consoleCommand);
    return;
  }
  const deleteButton = event.target.closest("button[data-delete]");
  if (deleteButton) {
    const currentName = deleteButton.closest("article")?.querySelector("h2")?.textContent || "Dekoder";
    deleteDevice(deleteButton.dataset.device, currentName);
    return;
  }
  const renameButton = event.target.closest("button[data-rename]");
  if (renameButton) {
    const currentName = renameButton.closest(".device-name")?.querySelector("h2")?.textContent || "Dekoder";
    renameDevice(renameButton.dataset.device, currentName);
    return;
  }
  const button = event.target.closest("button[data-action]");
  if (button) queueAction(button.dataset.device, button.dataset.action);
  const captchaButton = event.target.closest("button[data-captcha]");
  if (captchaButton) startCaptchaSession(captchaButton.dataset.device);
};
$("#pair").onclick = async () => {
  try {
    const data = await request("/v1/admin/pairings", { method: "POST", body: "{}" });
    $("#notice").textContent = `4-cyfrowy kod ważny 15 min: ${data.pairingCode}. Wpisz go w ustawieniach E2-Foorys na dekoderze.`;
  } catch (error) { $("#notice").textContent = error.message; }
};

if (password) { $("#password").value = password; login(); }
window.setInterval(() => { if (password && !document.hidden) load(); }, 15000);
