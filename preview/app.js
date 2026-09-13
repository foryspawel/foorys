(function () {
  "use strict";

  var sections = [
    { id: "channels", title: "Listy kanałów", description: "Wybierz i zainstaluj listę kanałów z centralnej bazy." },
    { id: "updates", title: "Aktualizacja pluginu", description: "Sprawdź GitHuba i zaktualizuj E2-Foorys." },
    { id: "iptv", title: "Foorys IPTV", description: "Europe Package, Polskie IPTV i automatyczne picony z playlisty." },
    { id: "picons", title: "Picony", description: "Aktualizacja piconów z centralnej bazy." },
    { id: "softcam", title: "Softcam / OSCam", description: "Oscam stable, EMU, NCam, CCcam i oscam.dvbapi." },
    { id: "plugins", title: "Wtyczki / Feedy", description: "Instalacja E2iPlayera i pakietów z centralnej bazy." },
    { id: "backups", title: "Kopie / Przywracanie", description: "Kopie bezpieczeństwa konfiguracji dekodera." },
    { id: "system", title: "System / Konserwacja", description: "Kondycja dekodera, root i ustawienia." },
    { id: "diagnostics", title: "Diagnostyka / Naprawa", description: "Raport, wolne miejsce i pakiety." }
  ];

  var tiles = [
    ["channels", "LISTY KANAŁÓW", "Foorys • Bzyk83 • 13E", "◫"],
    ["updates", "AKTUALIZACJE", "Plugin i katalog GitHub", "↻"],
    ["iptv", "FOORYS IPTV", "Kanały IPTV", "▶"],
    ["picons", "PICONY", "Pobieranie piconów", "✦"],
    ["softcam", "OSCAM / SOFTCAM", "Stable • EMU • NCam", "◎"],
    ["plugins", "PLUGINY", "E2iPlayer • XStreamity", "✣"],
    ["backups", "KOPIE ZAPASOWE", "Dostępne kopie plików", "▦"],
    ["system", "SYSTEM", "Miejsce • Root • GUI", "⚙"],
    ["diagnostics", "DIAGNOSTYKA", "CPU • RAM • RootFS", "⌁"]
  ];

  var fallbackManifest = {
    channel_lists: [
      { id: "foorys-hotbird-13e", name: "Foorys Hotbird 13E", description: "Jeden bukiet Foorys z polskimi kanałami na Hotbirdzie 13E.", satellites: "Hotbird 13E", version: "2026.09.13" },
      { id: "bzyk83-hotbird-13e", name: "Bzyk83 Hotbird 13E", description: "Oryginalna lista Bzyk83 dla satelity Hotbird 13E.", satellites: "Hotbird 13E", version: "2026.08.23" },
      { id: "bzyk83-dual", name: "Bzyk83 Dual", description: "Oryginalna lista Bzyk83 dla Hotbird 13E i Astra 19.2E.", satellites: "Hotbird 13E + Astra 19.2E", version: "2026.08.23" }
    ],
    plugins: [
      { id: "xstreamity", name: "XStreamity", description: "Odtwarzacz IPTV dla Enigma2.", version: "5.58" },
      { id: "chocholousek-picons", name: "Chocholousek Picons", description: "Narzędzia i obsługa piconów.", version: "5.0.240904" }
    ],
    picons: [
      { id: "chocholousek-13e", name: "Chocholousek Picons 220x132 13.0E", description: "Transparentne picony dla Hotbirda 13E.", version: "2026.01.07" },
      { id: "chocholousek-19e", name: "Chocholousek Picons 220x132 19.2E", description: "Transparentne picony dla Astry 19.2E.", version: "2026.01.07" }
    ],
      plugin_update: { id: "e2foorys", name: "E2-Foorys", description: "Aktualizacja panelu E2-Foorys z GitHuba.", version: "0.6.6" }
  };

  var state = { selected: 0, manifest: fallbackManifest, entries: [], entryIndex: 0, activeSection: null, consoleTimer: null };
  var $ = function (selector) { return document.querySelector(selector); };

  function setStatus(text) { $("#status").textContent = text; }

  function renderClock() {
    var now = new Date();
    var pad = function (value) { return String(value).padStart(2, "0"); };
    $("#clock").textContent = pad(now.getDate()) + "." + pad(now.getMonth() + 1) + "." + now.getFullYear() + "  " + pad(now.getHours()) + ":" + pad(now.getMinutes()) + ":" + pad(now.getSeconds());
  }

  function renderTiles() {
    var grid = $("#card-grid");
    grid.innerHTML = "";
    tiles.forEach(function (tile, index) {
      var button = document.createElement("button");
      button.className = "tile" + (index === state.selected ? " selected" : "");
      button.setAttribute("role", "option");
      button.setAttribute("aria-selected", index === state.selected ? "true" : "false");
      button.setAttribute("aria-label", tile[1] + ": " + tile[2]);
      button.innerHTML = "<span class=\"tile-accent\"></span><span class=\"tile-icon\" aria-hidden=\"true\">" + tile[3] + "</span><span class=\"tile-content\"><span class=\"tile-number\">" + String(index + 1).padStart(2, "0") + (index === state.selected ? " • WYBRANE" : "") + "</span><span class=\"tile-title\">" + tile[1] + "</span><span class=\"tile-hint\">" + (index === state.selected ? "ENTER — otwórz kategorię" : tile[2]) + "</span></span>";
      button.addEventListener("click", function () { selectTile(index); });
      button.addEventListener("dblclick", function () { openSection(index); });
      button.addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openSection(index); } });
      grid.appendChild(button);
    });
  }

  function selectTile(index) {
    if (index < 0 || index >= sections.length) return;
    state.selected = index;
    $("#focus-title").textContent = "WYBRANO  " + String(index + 1).padStart(2, "0") + "  " + sections[index].title.toUpperCase();
    renderTiles();
  }

  function item(title, description, meta, id, action) {
    return { title: title, description: description || "", meta: meta || "", id: id || "demo", action: action || "install" };
  }

  function buildEntries(sectionId) {
    var manifest = state.manifest || fallbackManifest;
    if (sectionId === "channels") {
      return (manifest.channel_lists || []).map(function (entry) { return item(entry.name, entry.description, entry.satellites + " • wersja " + entry.version, entry.id, "install"); });
    }
    if (sectionId === "updates") {
      return [item("SPRAWDŹ I ZAKTUALIZUJ TERAZ", "Pobiera katalog GitHub i sprawdza najnowszą wersję pluginu.", "Skrót: NIEBIESKI", "quick-update", "install"), item("Odśwież katalog z GitHuba", "Pobiera świeży manifest i odświeża wszystkie zakładki.", "Skrót: ZIELONY", "refresh", "refresh"), item("E2-Foorys jest aktualny [0.6.6]", "W podglądzie lokalnym nie instalujemy pakietu.", "Wersja demonstracyjna", "current", "info")];
    }
    if (sectionId === "iptv") return [
      item("Instaluj listę Foorys IPTV", "Pobiera playlistę M3U i tworzy osobny bukiet. Picony są opcjonalne i pobierane osobno.", "Bukiet główny", "foorys-iptv", "install"),
      item("Konfiguracja Foorys IPTV", "W dekoderze wpisz prywatny link M3U albo DNS, login i hasło. Dane zostają wyłącznie lokalnie.", "MENU → Ustawienia", "iptv-settings", "settings"),
      item("Pobierz picony IPTV osobno", "Pobiera picony z playlisty do katalogu piconów. Operacja jest dobrowolna.", "tvg-logo", "iptv-picons", "install")
    ];
    if (sectionId === "picons") {
      return (manifest.picons || []).map(function (entry) { return item(entry.name, entry.description, "Wersja " + entry.version, entry.id, "install"); }).concat([item("Odśwież katalog piconów", "Pobiera aktualne dane z centralnej bazy.", "ZIELONY", "picons-refresh", "refresh")]);
    }
    if (sectionId === "softcam") return [
      item("Instaluj Oscam stable", "Feed OEA, opkg update i instalacja Oscam stable.", "OEA feed", "oscam-stable", "install"),
      item("Instaluj OSCam-emu", "Publiczny pakiet z feedu OEA. Do legalnych uprawnień odbioru.", "OEA feed", "oscam-emu", "install"),
      item("Instaluj NCam", "Publiczny pakiet z feedu OEA. Do legalnych uprawnień odbioru.", "OEA feed", "ncam", "install"),
      item("Instaluj CCcam 2.3.9", "Publiczny pakiet z feedu OEA. Do legalnych uprawnień odbioru.", "OEA feed", "cccam-2.3.9", "install"),
      item("Pobierz aktualny oscam.dvbapi", "Zapisze wyłącznie P:1884, P:0B01 i P:1861.", "Foorys current", "oscam-dvbapi", "install")
    ];
    if (sectionId === "plugins") return [
      item("Instaluj E2iPlayer (Python 3)", "Oficjalny instalator E2iPlayera dla Python 3.", "OE-Mirrors", "e2iplayer", "install"),
      item("Patch E2iPlayer (hosttorrentyts)", "Patch dla wcześniej zainstalowanego E2iPlayera.", "hosttorrentyts", "e2iplayer-patch", "install")
    ].concat((manifest.plugins || []).map(function (entry) { return item(entry.name, entry.description, "Wersja " + entry.version, entry.id, "install"); }));
    if (sectionId === "backups") return [item("Pokaż dostępne kopie", "Wyświetla kopie list kanałów i oscam.dvbapi.", "Podgląd raportu", "backups", "install"), item("Otwórz ustawienia ścieżek", "Katalog kopii zmienisz w ustawieniach.", "Konfiguracja", "settings", "settings")];
    if (sectionId === "system") return [item("Sprawdź kondycję dekodera", "Model, obraz, CPU, RAM, flash, temperatura i uptime.", "Dane demonstracyjne", "health", "install"), item("Sprawdź wolne miejsce", "Wolne miejsce na rootfs i magazynie danych.", "Dane demonstracyjne", "free-space", "install"), item("Restart GUI Enigma2", "Restart interfejsu po potwierdzeniu.", "Nieaktywne w podglądzie", "restart", "info"), item("Zmień hasło root", "Dwukrotne wpisanie nowego hasła i końcowe potwierdzenie.", "Formularz demonstracyjny", "root-password", "password"), item("Ustawienia E2-Foorys", "GitHub, ścieżki docelowe i kopie bezpieczeństwa.", "Konfiguracja", "settings", "settings")];
    if (sectionId === "diagnostics") return [item("Pełna diagnostyka dekodera", "Otwiera szczegółowy raport parametrów systemu.", "Dane demonstracyjne", "health", "install"), item("Wolne miejsce / magazyn", "Kontroluje rootfs oraz dysk HDD/USB.", "Dane demonstracyjne", "free-space", "install"), item("Diagnostyka sieci", "Sprawdza interfejs, bramę, DNS i połączenie HTTPS z centralną bazą.", "Test bieżący", "network-diagnostic", "install"), item("Diagnostyka połączenia satelitarnego", "Sprawdza wykryte tunery DVB, blokadę sygnału, SNR/AGC i BER.", "Test bieżący", "satellite-diagnostic", "install"), item("Zainstalowane pakiety softcam", "Pokazuje znalezione pakiety.", "Dane demonstracyjne", "packages", "install"), item("Odśwież dane diagnostyczne", "Ponownie odczytuje parametry.", "ZIELONY", "diagnostics-refresh", "refresh")];
    return [];
  }

  function openSection(index) {
    selectTile(index);
    state.activeSection = sections[index].id;
    state.entries = buildEntries(state.activeSection);
    state.entryIndex = 0;
    $("#catalog-title").textContent = sections[index].title;
    $("#catalog-modal").classList.add("open");
    $("#catalog-modal").setAttribute("aria-hidden", "false");
    renderCatalog();
  }

  function renderCatalog() {
    var list = $("#catalog-list");
    list.innerHTML = "";
    state.entries.forEach(function (entry, index) {
      var button = document.createElement("button");
      button.className = "catalog-item" + (index === state.entryIndex ? " selected" : "");
      button.innerHTML = "<span class=\"catalog-item-title\">" + entry.title + "</span><span class=\"catalog-item-meta\">" + entry.meta + "</span>";
      button.addEventListener("click", function () { state.entryIndex = index; renderCatalog(); });
      list.appendChild(button);
    });
    var entry = state.entries[state.entryIndex];
    if (!entry) {
      $("#detail-title").textContent = "Brak pozycji";
      $("#detail-description").textContent = "Brak czynności do pokazania.";
      $("#detail-meta").textContent = "—";
      return;
    }
    $("#detail-title").textContent = entry.title;
    $("#detail-description").textContent = entry.description;
    $("#detail-meta").textContent = entry.meta;
    $("#run-action").textContent = entry.action === "info" ? "ZAMKNIJ INFORMACJĘ" : entry.action === "password" ? "OTWÓRZ FORMULARZ" : "OK — uruchom podgląd";
    var selected = list.querySelector(".selected");
    if (selected) selected.scrollIntoView({ block: "nearest" });
  }

  function closeModal(id) {
    var modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
  }

  function closeCatalog() { closeModal("catalog-modal"); }

  function runAction() {
    var entry = state.entries[state.entryIndex];
    if (!entry) return;
    if (entry.action === "info") { closeCatalog(); return; }
    if (entry.action === "password") { closeCatalog(); openPassword(); return; }
    if (entry.action === "settings") { closeCatalog(); runDemo(item("Ustawienia E2-Foorys", "Podgląd ustawień centralnego repozytorium.", "Tryb lokalny", "settings-demo", "install")); return; }
    if (entry.action === "refresh") { closeCatalog(); loadManifest(); return; }
    closeCatalog();
    runDemo(entry);
  }

  function runDemo(entry) {
    closeModal("console-modal");
    $("#console-title").textContent = entry.title;
    $("#console-log").innerHTML = "";
    $("#console-result").className = "console-result";
    $("#console-result").textContent = "OPERACJA W TOKU...";
    $("#console-modal").classList.add("open");
    $("#console-modal").setAttribute("aria-hidden", "false");
    setStatus("Podgląd: " + entry.title + "...");
    var lines = ["E2-Foorys: rozpoczynam operację.", "Element: " + entry.title, "Tryb lokalny: dekoder nie jest używany.", "Sprawdzam dane i przygotowuję instalację..."];
    var index = 0;
    var write = function () {
      if (index >= lines.length) {
        $("#console-result").className = "console-result success";
        $("#console-result").textContent = "POWODZENIE: podgląd zakończony — w realnej wtyczce pojawi się wynik systemu.";
        setStatus("Podgląd zakończony pomyślnie.");
        return;
      }
      var line = document.createElement("div");
      line.className = "console-line";
      line.textContent = lines[index++];
      $("#console-log").appendChild(line);
      $("#console-log").scrollTop = $("#console-log").scrollHeight;
      state.consoleTimer = window.setTimeout(write, 400);
    };
    write();
  }

  function openPassword() {
    $("#password-form").reset();
    $("#password-error").textContent = "";
    $("#password-modal").classList.add("open");
    $("#password-modal").setAttribute("aria-hidden", "false");
    window.setTimeout(function () { $("#password-one").focus(); }, 50);
  }

  function submitPassword(event) {
    event.preventDefault();
    var one = $("#password-one").value;
    var two = $("#password-two").value;
    if (one.length < 8) { $("#password-error").textContent = "Hasło musi mieć co najmniej 8 znaków."; return; }
    if (one !== two) { $("#password-error").textContent = "Hasła nie są identyczne."; return; }
    closeModal("password-modal");
    runDemo(item("Zmiana hasła root", "W podglądzie lokalnym zmiana jest symulowana.", "Podwójne potwierdzenie OK", "root-password-demo", "install"));
  }

  function loadManifest() {
    setStatus("Pobieranie manifestu do podglądu...");
    fetch("/manifest.json?preview=" + Date.now(), { cache: "no-store" }).then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    }).then(function (manifest) {
      state.manifest = manifest;
      setStatus("Katalog lokalny OK: " + (manifest.channel_lists || []).length + " list, " + (manifest.plugins || []).length + " pluginów.");
    }).catch(function () {
      state.manifest = fallbackManifest;
      setStatus("Tryb lokalny: używam danych demonstracyjnych.");
    });
  }

  function refreshMetrics() {
    var cpu = 8 + Math.floor(Math.random() * 10);
    var ram = 49 + Math.floor(Math.random() * 5);
    $("#cpu-value").textContent = cpu + "%";
    $("#ram-value").textContent = ram + "%";
  }

  function handleKeys(event) {
    if ($("#password-modal").classList.contains("open") || $("#console-modal").classList.contains("open")) {
      if (event.key === "Escape") { closeModal("password-modal"); closeModal("console-modal"); }
      return;
    }
    if ($("#catalog-modal").classList.contains("open")) {
      if (event.key === "ArrowDown") { event.preventDefault(); state.entryIndex = Math.min(state.entryIndex + 1, state.entries.length - 1); renderCatalog(); }
      if (event.key === "ArrowUp") { event.preventDefault(); state.entryIndex = Math.max(state.entryIndex - 1, 0); renderCatalog(); }
      if (event.key === "Enter") { event.preventDefault(); runAction(); }
      if (event.key === "Escape") { closeCatalog(); }
      return;
    }
    var next = state.selected;
    if (event.key === "ArrowRight") next += 1;
    if (event.key === "ArrowLeft") next -= 1;
    if (event.key === "ArrowDown") next += 3;
    if (event.key === "ArrowUp") next -= 3;
    if (next !== state.selected) { event.preventDefault(); selectTile(next); }
    if (event.key === "Enter") { event.preventDefault(); openSection(state.selected); }
    if (event.key.toLowerCase() === "g") { loadManifest(); }
    if (event.key.toLowerCase() === "b") { runDemo(item("Szybka aktualizacja E2-Foorys", "Podgląd aktualizacji pluginu.", "NIEBIESKI", "quick-update", "install")); }
    if (event.key.toLowerCase() === "m") { openSection(7); }
  }

  document.addEventListener("keydown", handleKeys);
  $("#run-action").addEventListener("click", runAction);
  $("#password-form").addEventListener("submit", submitPassword);
  $("#refresh-button").addEventListener("click", loadManifest);
  $("#quick-update-button").addEventListener("click", function () { runDemo(item("Szybka aktualizacja E2-Foorys", "Podgląd aktualizacji pluginu.", "NIEBIESKI", "quick-update", "install")); });
  $("#settings-button").addEventListener("click", function () { openSection(7); });
  $("#console-close").addEventListener("click", function () { closeModal("console-modal"); });
  document.querySelectorAll("[data-close]").forEach(function (button) { button.addEventListener("click", function () { closeModal(button.getAttribute("data-close")); }); });

  renderClock();
  window.setInterval(renderClock, 1000);
  window.setInterval(refreshMetrics, 2800);
  renderTiles();
  loadManifest();
}());
