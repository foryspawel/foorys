# -*- coding: utf-8 -*-

"""Panel E2-Foorys z zakładkami i diagnostyką dekodera."""

from __future__ import absolute_import

import os
import time

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from .config import central_manifest_url, ensure_config, settings_dict
from .core import version_is_newer
from .operations import (
    collect_installed_packages,
    collect_system_status,
    fetch_manifest,
    install_channel_list,
    install_current_oscam_dvbapi,
    install_e2iplayer,
    install_oscam_dvbapi,
    install_oscam_stable,
    install_picons,
    install_plugin_package,
    list_backups,
    patch_e2iplayer,
)
from .ui import AsyncJob, CatalogScreen


VERSION = "0.4.0"


MAIN_SKIN = """
<screen name="E2FoorysMain" position="center,center" size="1260,700" title="E2-Foorys" backgroundColor="#06101B" borderWidth="2" borderColor="#1683BB">
    <eLabel position="0,0" size="1260,5" backgroundColor="#26C8F5" />
    <eLabel position="26,18" size="4,74" backgroundColor="#26C8F5" />
    <widget name="logo" position="44,20" size="70,70" alphatest="blend" scale="1" />
    <widget name="title" position="132,20" size="620,42" font="Regular;34" foregroundColor="#F2F7FC" backgroundColor="#0B1827" transparent="0" />
    <widget name="subtitle" position="132,63" size="620,28" font="Regular;20" foregroundColor="#8FA7BE" backgroundColor="#0B1827" transparent="0" />
    <widget name="version" position="890,18" size="338,26" font="Regular;21" foregroundColor="#28C8F5" backgroundColor="#0B1827" transparent="0" horizontalAlignment="right" />
    <widget name="clock" position="890,47" size="338,27" font="Regular;22" foregroundColor="#C0D0DE" backgroundColor="#0B1827" transparent="0" horizontalAlignment="right" />
    <widget name="top_stats" position="890,77" size="338,24" font="Regular;18" foregroundColor="#55D6A0" backgroundColor="#0B1827" transparent="0" horizontalAlignment="right" />
    <widget name="shortcut" position="890,103" size="338,24" font="Regular;17" foregroundColor="#FFD24A" backgroundColor="#0B1827" transparent="0" horizontalAlignment="right" />
    <eLabel position="26,132" size="1208,1" backgroundColor="#173049" />
    <widget name="focus_title" position="36,145" size="560,32" font="Regular;27" foregroundColor="#26C8F5" backgroundColor="#0B1827" transparent="0" />
    <widget name="focus_desc" position="610,145" size="614,32" font="Regular;19" foregroundColor="#9DB2C5" backgroundColor="#0B1827" transparent="0" horizontalAlignment="right" />

    <eLabel position="32,182" size="380,106" backgroundColor="#0C1B2B" />
    <eLabel position="32,182" size="5,106" backgroundColor="#26C8F5" />
    <eLabel position="440,182" size="380,106" backgroundColor="#0C1B2B" />
    <eLabel position="440,182" size="5,106" backgroundColor="#B97CFF" />
    <eLabel position="848,182" size="380,106" backgroundColor="#0C1B2B" />
    <eLabel position="848,182" size="5,106" backgroundColor="#55D6A0" />
    <eLabel position="32,302" size="380,106" backgroundColor="#0C1B2B" />
    <eLabel position="32,302" size="5,106" backgroundColor="#FFB347" />
    <eLabel position="440,302" size="380,106" backgroundColor="#0C1B2B" />
    <eLabel position="440,302" size="5,106" backgroundColor="#F06BCB" />
    <eLabel position="848,302" size="380,106" backgroundColor="#0C1B2B" />
    <eLabel position="848,302" size="5,106" backgroundColor="#4EA7FF" />
    <eLabel position="32,422" size="380,106" backgroundColor="#0C1B2B" />
    <eLabel position="32,422" size="5,106" backgroundColor="#9A8CFF" />
    <eLabel position="440,422" size="380,106" backgroundColor="#0C1B2B" />
    <eLabel position="440,422" size="5,106" backgroundColor="#FFC857" />
    <eLabel position="848,422" size="380,106" backgroundColor="#0C1B2B" />
    <eLabel position="848,422" size="5,106" backgroundColor="#FF6B6B" />

    <widget name="card0" position="50,193" size="350,84" font="Regular;21" foregroundColor="#D8E3ED" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="card1" position="458,193" size="350,84" font="Regular;21" foregroundColor="#D8E3ED" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="card2" position="866,193" size="350,84" font="Regular;21" foregroundColor="#D8E3ED" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="card3" position="50,313" size="350,84" font="Regular;21" foregroundColor="#D8E3ED" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="card4" position="458,313" size="350,84" font="Regular;21" foregroundColor="#D8E3ED" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="card5" position="866,313" size="350,84" font="Regular;21" foregroundColor="#D8E3ED" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="card6" position="50,433" size="350,84" font="Regular;21" foregroundColor="#D8E3ED" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="card7" position="458,433" size="350,84" font="Regular;21" foregroundColor="#D8E3ED" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="card8" position="866,433" size="350,84" font="Regular;21" foregroundColor="#D8E3ED" backgroundColor="#0C1B2B" transparent="0" />

    <eLabel position="26,548" size="1208,1" backgroundColor="#173049" />
    <widget name="decoder" position="36,560" size="590,31" font="Regular;18" foregroundColor="#55D6A0" backgroundColor="#0B1827" transparent="0" />
    <widget name="status" position="650,560" size="574,31" font="Regular;19" foregroundColor="#FFD24A" backgroundColor="#0B1827" transparent="0" horizontalAlignment="right" />
    <widget name="hint" position="36,606" size="1188,54" font="Regular;19" foregroundColor="#8CA2B5" backgroundColor="#0B1827" transparent="0" />
</screen>
"""


HEALTH_SKIN = """
<screen name="E2FoorysHealth" position="center,center" size="1120,650" title="E2-Foorys - kondycja dekodera" backgroundColor="#06101B" borderWidth="2" borderColor="#1683BB">
    <widget name="title" position="32,22" size="1055,50" font="Regular;36" foregroundColor="#18C7F5" />
    <widget name="report" position="38,88" size="1045,475" font="Regular;27" foregroundColor="#D8E3ED" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="status" position="38,575" size="1045,32" font="Regular;23" foregroundColor="#FFD24A" />
    <widget name="hint" position="38,613" size="1045,27" font="Regular;20" foregroundColor="#71899E" />
</screen>
"""


SECTION_MENU_SKIN = """
<screen name="E2FoorysSectionMenu" position="center,center" size="1120,650" title="E2-Foorys" backgroundColor="#06101B" borderWidth="2" borderColor="#1683BB">
    <eLabel position="0,0" size="1120,5" backgroundColor="#26C8F5" />
    <widget name="title" position="32,22" size="1045,46" font="Regular;36" foregroundColor="#F2F7FC" backgroundColor="#0B1827" transparent="0" />
    <widget name="description" position="32,70" size="1045,34" font="Regular;21" foregroundColor="#8FA7BE" backgroundColor="#0B1827" transparent="0" />
    <eLabel position="32,118" size="1045,1" backgroundColor="#173049" />
    <widget name="list" position="32,140" size="690,390" itemHeight="58" font="Regular;25" scrollbarMode="showOnDemand" foregroundColor="#D8E3ED" foregroundColorSelected="#FFFFFF" backgroundColor="#0C1B2B" backgroundColorSelected="#174D68" transparent="0" />
    <widget name="item_title" position="754,140" size="323,40" font="Regular;26" foregroundColor="#26C8F5" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="item_info" position="754,190" size="323,210" font="Regular;21" foregroundColor="#B8C9D8" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="status" position="32,552" size="1045,34" font="Regular;22" foregroundColor="#FFD24A" backgroundColor="#0B1827" transparent="0" />
    <widget name="hint" position="32,604" size="1045,30" font="Regular;20" foregroundColor="#8CA2B5" backgroundColor="#0B1827" transparent="0" />
</screen>
"""


SECTIONS = (
    ("channels", "Listy kanałów", "Pobieranie i bezpieczna instalacja list kanałów."),
    ("updates", "Aktualizacja pluginu", "Sprawdzenie GitHuba i aktualizacja E2-Foorys jednym przyciskiem."),
    ("iptv", "IPTV / Odtwarzacze", "Instalacja E2iPlayera oraz jego patcha."),
    ("picons", "Picony", "Automatyczna aktualizacja piconów z centralnej bazy."),
    ("softcam", "Softcam / OSCam", "Oscam stable, oscam.dvbapi i kontrola softcamów."),
    ("plugins", "Wtyczki / Feedy", "Pakiety IPK/DEB z własnego manifestu."),
    ("backups", "Kopie / Przywracanie", "Kopie bezpieczeństwa konfiguracji."),
    ("system", "System / Konserwacja", "Podstawowe operacje administracyjne GUI."),
    ("diagnostics", "Diagnostyka / Naprawa", "Kondycja, wolne miejsce i pakiety."),
)


def _format_size(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "n/d"
    units = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while abs(value) >= 1024 and index < len(units) - 1:
        value /= 1024.0
        index += 1
    return "%d %s" % (int(value), units[index]) if index == 0 else "%.1f %s" % (value, units[index])


def _format_uptime(seconds):
    try:
        seconds = max(int(seconds), 0)
    except (TypeError, ValueError):
        return "n/d"
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    return "%dd %02dh %02dm" % (days, hours, minutes) if days else "%02dh %02dm" % (hours, minutes)


def _short_description(value, width=39, limit=7):
    words = str(value or "").replace("\r", "").split()
    lines = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if not lines:
        lines = [""]
    return "\n".join(lines[:limit])


def _friendly_manifest_error(error):
    """Zamienia techniczny błąd manifestu na komunikat dla użytkownika."""

    text = str(error or "Nieznany błąd.")
    lowered = text.lower()
    if "sha256" in lowered or "suma" in lowered:
        return (
            "Centralny katalog zawiera błędny wpis sumy pliku.\n"
            "Aktualizacja nie została uruchomiona. Poprawka repozytorium jest "
            "w przygotowaniu — spróbuj ponownie przyciskiem ZIELONY.\n\n"
            "Szczegóły: %s" % text
        )
    if "manifest" in lowered or "json" in lowered:
        return (
            "Nie można odczytać centralnego katalogu GitHub.\n"
            "Sprawdź połączenie z internetem i spróbuj ponownie przyciskiem "
            "ZIELONY.\n\nSzczegóły: %s" % text
        )
    return "Nie można połączyć z centralną bazą GitHub.\n\nSzczegóły: %s" % text


def _entry_label(entry):
    return "%s  [%s]" % (
        entry.get("name", entry.get("id", "?")),
        entry.get("version", "?"),
    )


class E2FoorysMain(Screen):
    skin = MAIN_SKIN

    def __init__(self, session):
        Screen.__init__(self, session)
        ensure_config()
        self.session = session
        self.manifest = None
        self.system_status = None
        self.section_index = 0
        self.card_index = 0
        self.manifest_job = None
        self.system_job = None
        self.action_job = None
        self.closed = False
        self.quick_update_requested = False
        self["logo"] = Pixmap()
        self["title"] = Label("E2-Foorys")
        self["subtitle"] = Label("Twoje narzędzia do Enigma2")
        self["version"] = Label("Foorys v%s" % VERSION)
        self["clock"] = Label("")
        self["shortcut"] = Label("NIEBIESKI: SZYBKA AKTUALIZACJA")
        self["focus_title"] = Label("")
        self["focus_desc"] = Label("")
        for index in range(len(SECTIONS)):
            self["card%d" % index] = Label("")
        self["top_stats"] = Label("CPU: --   RAM: --")
        self["decoder"] = Label("Odczytywanie stanu dekodera...")
        self["status"] = Label("Łączenie z centralną bazą GitHub...")
        self["hint"] = Label("STRZAŁKI: wybierz kafelek   OK: otwórz   ZIELONY: odśwież   NIEBIESKI: szybka aktualizacja   MENU: ustawienia   EXIT: zamknij")
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions", "MenuActions", "ColorActions"],
            {
                "ok": self.select,
                "cancel": self.close_screen,
                "menu": self.open_settings,
                "up": self.move_up,
                "down": self.move_down,
                "left": self.move_left,
                "right": self.move_right,
                "pageUp": self.move_page_up,
                "pageDown": self.move_page_down,
                "green": self.refresh_all,
                "blue": self.quick_update,
                "info": self.show_health,
            },
            -1,
        )
        self.onClose.append(self._on_close)
        self.onLayoutFinish.append(self._layout_ready)
        self._render_cards()
        self._refresh_system_status()
        self._refresh_manifest()

    def _layout_ready(self):
        try:
            path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "foorys.png")
            if self["logo"].instance is not None and os.path.exists(path):
                self["logo"].instance.setPixmapFromFile(path)
                self["logo"].show()
        except Exception:
            pass
        self._update_clock()
        self._render_cards()

    def _update_clock(self):
        self["clock"].setText(time.strftime("%d.%m.%Y  %H:%M"))

    def _on_close(self):
        self.closed = True
        for job in (self.manifest_job, self.system_job, self.action_job):
            if job is not None:
                job.stop()

    def close_screen(self):
        for job in (self.manifest_job, self.system_job, self.action_job):
            if job is not None and job.running:
                self.session.open(MessageBox, "Operacja jeszcze trwa.", MessageBox.TYPE_INFO, timeout=4)
                return
        self.close()

    def _render_cards(self):
        """Rysuje główny ekran jako niezależną siatkę narzędzi."""

        for index, section in enumerate(SECTIONS):
            title = section[1].upper()
            description = _short_description(section[2], width=36, limit=2)
            marker = "▶" if index == self.card_index else " "
            text = "%s %02d  %s\n%s" % (marker, index + 1, title, description)
            self["card%d" % index].setText(text)

        section_id, title, description = SECTIONS[self.card_index]
        self["focus_title"].setText("WYBRANO  %02d  %s" % (self.card_index + 1, title.upper()))
        self["focus_desc"].setText(_short_description(description, width=58, limit=1))

    def _move_card(self, delta):
        new_index = self.card_index + delta
        if 0 <= new_index < len(SECTIONS):
            self.card_index = new_index
            self.section_index = new_index
            self._render_cards()

    def move_left(self):
        if self.card_index % 3:
            self._move_card(-1)

    def move_right(self):
        if self.card_index % 3 < 2 and self.card_index + 1 < len(SECTIONS):
            self._move_card(1)

    def move_up(self):
        if self.card_index >= 3:
            self._move_card(-3)

    def move_down(self):
        if self.card_index + 3 < len(SECTIONS):
            self._move_card(3)

    def move_page_up(self):
        self._move_card(-3)

    def move_page_down(self):
        self._move_card(3)

    def _item(self, title, description, action, **extra):
        item = {"title": title, "description": description, "action": action}
        item.update(extra)
        return item

    def _install_item(self, title, description, entry, operation, catalog_title):
        return self._item(
            title or _entry_label(entry),
            description or entry.get("description", ""),
            "install",
            entry=entry,
            operation=operation,
            catalog_title=catalog_title,
        )

    def _manifest_refresh_item(self):
        return self._item("Odśwież katalog z GitHuba", "Pobiera manifest z repozytorium GitHub i odświeża zakładki.", "refresh")

    def _items_for_section(self, section_id):
        manifest = self.manifest or {}
        result = []
        if section_id == "channels":
            for entry in manifest.get("channel_lists", []):
                result.append(self._install_item(None, entry.get("description"), entry, install_channel_list, "Listy kanałów"))
            if not result:
                result.append(self._item("Brak list w centralnej bazie", "Centralne listy kanałów są publikowane w repozytorium Foorys. Aktualny adres bazy: %s" % central_manifest_url(), "info"))
            result.append(self._manifest_refresh_item())
        elif section_id == "updates":
            result.append(self._item("SPRAWDŹ I ZAKTUALIZUJ TERAZ", "Naciśnij OK, aby pobrać katalog i zainstalować najnowszą wersję E2-Foorys.", "quick_update"))
            result.append(self._manifest_refresh_item())
            update = manifest.get("plugin_update")
            if update and version_is_newer(update.get("version"), VERSION):
                result.append(self._install_item("Aktualizuj E2-Foorys  [%s]" % update.get("version"), update.get("description"), update, install_plugin_package, "Aktualizacja E2-Foorys"))
            elif update:
                result.append(self._item("E2-Foorys jest aktualny  [%s]" % VERSION, "GitHub nie udostępnia nowszej wersji pluginu.", "info"))
            else:
                result.append(self._item("Brak pakietu aktualizacji", "Manifest GitHub nie ma jeszcze obiektu plugin_update.", "info"))
            result.append(self._item("Centralna baza GitHub", central_manifest_url(), "info"))
        elif section_id == "iptv":
            result.extend([
                self._install_item("Instaluj E2iPlayer (Python 3)", "Oficjalny instalator E2iPlayer dla Python 3.", {"id": "e2iplayer", "name": "E2iPlayer", "version": "Python 3 / OE-Mirrors"}, install_e2iplayer, "Instalacja E2iPlayer"),
                self._install_item("Patch E2iPlayer (hosttorrentyts)", "Patch dla wcześniej zainstalowanego E2iPlayera.", {"id": "e2iplayer-patch", "name": "E2iPlayer patch", "version": "hosttorrentyts"}, patch_e2iplayer, "Patch E2iPlayer"),
            ])
        elif section_id == "picons":
            for entry in manifest.get("picons", []):
                result.append(self._install_item(None, entry.get("description"), entry, install_picons, "Aktualizacja piconów"))
            if not result:
                result.append(self._item("Brak pakietów piconów", "Centralna baza nie ma jeszcze opublikowanych archiwów piconów.", "info"))
            result.append(self._item("Katalog docelowy piconów", "Aktualna ścieżka: %s. Zmienisz ją przez MENU → Ustawienia." % settings_dict().get("picon_dir", "/usr/share/enigma2/picon"), "settings"))
            result.append(self._manifest_refresh_item())
        elif section_id == "softcam":
            result.append(self._install_item("Instaluj Oscam stable", "Feed OEA, opkg update i instalacja Oscam stable.", {"id": "oscam-stable", "name": "Oscam stable", "version": "OEA feed"}, install_oscam_stable, "Instalacja Oscam stable"))
            result.append(self._install_item("Pobierz aktualny oscam.dvbapi", "Zapisze dokładnie: P:1884, P:0B01, P:1861. Poprzedni plik zostanie zachowany w kopii.", {"id": "oscam-current", "name": "Aktualny oscam.dvbapi", "version": "Foorys current"}, install_current_oscam_dvbapi, "Aktualny oscam.dvbapi"))
            if manifest.get("oscam_dvbapi"):
                result.append(self._install_item(None, manifest["oscam_dvbapi"].get("description"), manifest["oscam_dvbapi"], install_oscam_dvbapi, "Aktualizacja oscam.dvbapi z manifestu"))
            result.append(self._item("Sprawdź zainstalowane softcamy", "Odczyta pakiety opkg zawierające Oscam, softcam lub E2iPlayer.", "packages"))
        elif section_id == "plugins":
            for entry in manifest.get("plugins", []):
                result.append(self._install_item(None, entry.get("description"), entry, install_plugin_package, "Instalacja pluginu"))
            if not result:
                result.append(self._item("Brak pluginów w manifeście", "Dodaj pakiety IPK/DEB do tablicy plugins w pliku manifest.json.", "info"))
            result.append(self._manifest_refresh_item())
        elif section_id == "backups":
            result.extend([
                self._item("Pokaż dostępne kopie", "Wyświetla kopie list kanałów i oscam.dvbapi zapisane przed podmianą.", "backups"),
                self._item("Otwórz ustawienia ścieżek", "Katalog kopii oraz opcję backupu zmienisz w Ustawieniach.", "settings"),
                self._item("Przywracanie kopii — następny etap", "Katalog i format kopii są już przygotowane; przywracanie dodamy w kolejnym kroku.", "info"),
            ])
        elif section_id == "system":
            result.extend([
                self._item("Sprawdź kondycję dekodera", "Model, obraz, CPU, RAM, flash, temperatura i uptime.", "health"),
                self._item("Sprawdź wolne miejsce", "Wolne miejsce na rootfs oraz status magazynu danych.", "free_space"),
                self._item("Restart GUI Enigma2", "Restart interfejsu po dodatkowym potwierdzeniu.", "restart_gui"),
                self._item("Ustawienia E2-Foorys", "GitHub, manifest, ścieżki docelowe i kopie bezpieczeństwa.", "settings"),
            ])
        elif section_id == "diagnostics":
            result.extend([
                self._item("Pełna diagnostyka dekodera", "Otwiera szczegółowy raport parametrów systemu.", "health"),
                self._item("Wolne miejsce / magazyn", "Kontroluje rootfs oraz wskazany dysk HDD/USB.", "free_space"),
                self._item("Zainstalowane pakiety softcam", "Pokazuje znalezione pakiety Oscam, softcam i E2iPlayer.", "packages"),
                self._item("Odśwież dane diagnostyczne", "Ponownie odczytuje parametry bez zmiany konfiguracji.", "system_refresh"),
            ])
        return result

    def _render_section(self):
        """Kompatybilny alias dla odświeżenia siatki po zmianie katalogu."""

        self._render_cards()

    def _manifest_url(self):
        return central_manifest_url()

    def _refresh_manifest(self):
        if self.manifest_job is not None and self.manifest_job.running:
            self["status"].setText("Katalog GitHub jest już pobierany...")
            return
        url = self._manifest_url()
        if not url:
            self["status"].setText("Ustaw repozytorium GitHub w MENU → Ustawienia.")
            return
        self["status"].setText("Pobieranie katalogu z GitHuba...")
        self.manifest_job = AsyncJob(self._manifest_finished)
        self.manifest_job.start(fetch_manifest, url)

    def _manifest_finished(self, result, error):
        self.manifest_job = None
        if self.closed:
            return
        quick_update_requested = self.quick_update_requested
        self.quick_update_requested = False
        if error:
            friendly_error = _friendly_manifest_error(error)
            if self.manifest is None:
                self._render_section()
            self["status"].setText("GitHub: nie udało się odświeżyć katalogu — poprzednie dane pozostają.")
            if quick_update_requested:
                self.session.open(MessageBox, friendly_error, MessageBox.TYPE_ERROR, timeout=14)
            return
        self.manifest = result
        self._render_section()
        self["status"].setText("GitHub OK: %d list, %d pluginów, %d pakietów piconów%s%s." % (len(result.get("channel_lists", [])), len(result.get("plugins", [])), len(result.get("picons", [])), ", oscam.dvbapi" if result.get("oscam_dvbapi") else "", ", aktualizacja" if result.get("plugin_update") else ""))
        if quick_update_requested:
            self._quick_update_from_manifest()

    def quick_update(self):
        """Skrót z niebieskiego przycisku: sprawdza i uruchamia aktualizację."""

        if self.action_job is not None and self.action_job.running:
            self["status"].setText("Inna operacja jest jeszcze uruchomiona.")
            return
        if self.manifest_job is not None and self.manifest_job.running:
            self["status"].setText("Sprawdzam już centralny katalog GitHub...")
            return
        self.quick_update_requested = True
        self._refresh_manifest()

    def _quick_update_from_manifest(self):
        update = (self.manifest or {}).get("plugin_update")
        if not update:
            self.session.open(
                MessageBox,
                "Centralna baza nie udostępnia pakietu aktualizacji E2-Foorys.\n\n"
                "Spróbuj ponownie później albo odśwież katalog przyciskiem ZIELONY.",
                MessageBox.TYPE_INFO,
                timeout=10,
            )
            return
        if version_is_newer(update.get("version"), VERSION):
            self.session.open(
                CatalogScreen,
                "Szybka aktualizacja E2-Foorys",
                [update],
                install_plugin_package,
            )
            return
        self.session.open(
            MessageBox,
            "E2-Foorys jest aktualny (%s).\n\nW centralnej bazie nie ma nowszej wersji." % VERSION,
            MessageBox.TYPE_INFO,
            timeout=8,
        )

    def _refresh_system_status(self):
        if self.system_job is not None and self.system_job.running:
            return
        self.system_job = AsyncJob(self._system_finished)
        self.system_job.start(collect_system_status, settings_dict())

    def _system_finished(self, result, error):
        self.system_job = None
        if self.closed:
            return
        if error:
            self["top_stats"].setText("CPU: n/d   RAM: n/d")
            self["decoder"].setText("Nie udało się odczytać stanu")
            return
        self.system_status = result
        self._render_stats(result)

    def _render_stats(self, data):
        memory = data.get("memory", {})
        flash = data.get("flash", {})
        storage = data.get("storage", {})
        storage_status = "zamontowany: %d%% zajęte, wolne %s" % (storage.get("percent", 0), _format_size(storage.get("free", 0))) if storage.get("mounted", True) else "niezamontowany"
        self["top_stats"].setText("CPU: %d%%   RAM: %d%%   RootFS: %s wolne" % (data.get("cpu_percent", 0), memory.get("percent", 0), _format_size(flash.get("free", 0))))
        self["decoder"].setText("%s | %s | %s" % (data.get("model", "n/d"), data.get("version", "n/d"), "Enigma2 OK" if data.get("enigma2_running") else "Enigma2?"))

    def refresh_all(self):
        self._update_clock()
        self._refresh_system_status()
        self._refresh_manifest()

    def select(self):
        section_id, title, description = SECTIONS[self.card_index]
        self.section_index = self.card_index
        self.session.open(SectionMenuScreen, self, section_id, title, description)

    def open_settings(self):
        from .ui import E2FoorysConfig

        self.session.openWithCallback(self._settings_closed, E2FoorysConfig)

    def _settings_closed(self, _result=None):
        self._render_section()
        self._refresh_system_status()
        self._refresh_manifest()

    def show_health(self):
        self.session.open(HealthScreen, self.system_status)

    def _show_free_space(self):
        if not self.system_status:
            self._refresh_system_status()
            self["status"].setText("Odczytuję wolne miejsce...")
            return
        flash = self.system_status.get("flash", {})
        storage = self.system_status.get("storage", {})
        if storage.get("mounted", True):
            storage_message = "Zajęte: %s / %s (%d%%)\nWolne: %s" % (_format_size(storage.get("used", 0)), _format_size(storage.get("total", 0)), storage.get("percent", 0), _format_size(storage.get("free", 0)))
        else:
            storage_message = "Nie zamontowano docelowego magazynu (%s).\nPomiar zastępczy: %s" % (storage.get("path", "/media/hdd"), storage.get("mountpoint", storage.get("mount", "n/d")))
        message = "RootFS (%s)\nZajęte: %s / %s (%d%%)\nWolne: %s\n\nMagazyn (%s)\n%s" % (flash.get("mountpoint", flash.get("mount", "/")), _format_size(flash.get("used", 0)), _format_size(flash.get("total", 0)), flash.get("percent", 0), _format_size(flash.get("free", 0)), storage.get("path", storage.get("mount", "n/d")), storage_message)
        self.session.open(MessageBox, message, MessageBox.TYPE_INFO, timeout=12)

    def _show_packages(self):
        if self.action_job is not None and self.action_job.running:
            return
        self["status"].setText("Odczytywanie pakietów...")
        self.action_job = AsyncJob(self._packages_finished)
        self.action_job.start(collect_installed_packages, settings_dict())

    def _packages_finished(self, result, error):
        self.action_job = None
        if self.closed:
            return
        if error:
            self.session.open(MessageBox, "Nie udało się odczytać pakietów:\n%s" % error, MessageBox.TYPE_ERROR, timeout=10)
            return
        packages = result.get("packages", [])
        self.session.open(MessageBox, "\n".join(packages) if packages else "Nie znaleziono pakietów Oscam/softcam/E2iPlayer.", MessageBox.TYPE_INFO, timeout=15)
        self["status"].setText("Odczyt pakietów zakończony.")

    def _show_backups(self):
        try:
            result = list_backups(settings_dict())
        except Exception as exc:
            self.session.open(MessageBox, "Nie udało się odczytać kopii:\n%s" % exc, MessageBox.TYPE_ERROR, timeout=10)
            return
        if not result.get("backups"):
            message = "Brak kopii w katalogu:\n%s" % result.get("root", "")
        else:
            message = "Kopie: %s\n\n%s" % (result.get("root", ""), "\n".join("%s (%s)" % (entry["name"], entry.get("type", "backup")) for entry in result["backups"]))
        self.session.open(MessageBox, message, MessageBox.TYPE_INFO, timeout=15)

    def _confirm_restart(self):
        self.session.openWithCallback(self._restart_confirmed, MessageBox, "Zrestartować GUI Enigma2?", MessageBox.TYPE_YESNO, default=False)

    def _restart_confirmed(self, answer):
        if not answer:
            return
        try:
            from Screens.Standby import TryQuitMainloop

            self.session.open(TryQuitMainloop, 3)
        except Exception:
            self.session.open(MessageBox, "Uruchom ręcznie restart GUI Enigma2.", MessageBox.TYPE_INFO, timeout=8)


class SectionMenuScreen(Screen):
    """Lista czynności otwierana z kafelka głównego ekranu."""

    skin = SECTION_MENU_SKIN

    def __init__(self, session, controller, section_id, title, description):
        Screen.__init__(self, session)
        self.controller = controller
        self.section_id = section_id
        self.section_items = controller._items_for_section(section_id)
        self.closed = False
        self["title"] = Label("%02d  %s" % (controller.card_index + 1, title))
        self["description"] = Label(description)
        self["list"] = MenuList([(item.get("title", ""), item.get("action", "")) for item in self.section_items])
        self["item_title"] = Label("")
        self["item_info"] = Label("")
        self["status"] = Label("Wybierz czynność i naciśnij OK.")
        self["hint"] = Label("OK: otwórz   ZIELONY: odśwież dane   EXIT: wróć")
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions", "ColorActions"],
            {
                "ok": self.select,
                "cancel": self.close_screen,
                "up": self.move_up,
                "down": self.move_down,
                "pageUp": self.page_up,
                "pageDown": self.page_down,
                "green": self.refresh,
            },
            -1,
        )
        try:
            self["list"].onSelectionChanged.append(self._selection_changed)
        except AttributeError:
            pass
        self.onClose.append(self._on_close)
        if not self.section_items:
            self["status"].setText("Brak czynności w tej kategorii.")
        self._selection_changed()

    def _on_close(self):
        self.closed = True

    @staticmethod
    def _selected_index(widget):
        try:
            value = widget.getSelectedIndex()
            return int(value) if value is not None else -1
        except (AttributeError, TypeError, ValueError):
            return -1

    def _selection_changed(self):
        index = self._selected_index(self["list"])
        if 0 <= index < len(self.section_items):
            item = self.section_items[index]
            self["item_title"].setText(_short_description(item.get("title", ""), width=22, limit=2))
            self["item_info"].setText(_short_description(item.get("description", ""), width=28, limit=8))

    def move_up(self):
        try:
            self["list"].up()
        except AttributeError:
            pass
        self._selection_changed()

    def move_down(self):
        try:
            self["list"].down()
        except AttributeError:
            pass
        self._selection_changed()

    def page_up(self):
        try:
            self["list"].pageUp()
        except AttributeError:
            self.move_up()
        self._selection_changed()

    def page_down(self):
        try:
            self["list"].pageDown()
        except AttributeError:
            self.move_down()
        self._selection_changed()

    def close_screen(self):
        self.close()

    def refresh(self):
        self.controller.refresh_all()
        self["status"].setText("Odświeżam katalog i dane dekodera...")

    def select(self):
        index = self._selected_index(self["list"])
        if not 0 <= index < len(self.section_items):
            return
        item = self.section_items[index]
        action = item.get("action")
        if action == "refresh":
            self.close()
            self.controller._refresh_manifest()
        elif action == "quick_update":
            self.close()
            self.controller.quick_update()
        elif action == "install":
            self.session.open(
                CatalogScreen,
                item.get("catalog_title", "E2-Foorys"),
                [item.get("entry")],
                item.get("operation"),
            )
        elif action == "health":
            self.controller.show_health()
        elif action == "free_space":
            self.controller._show_free_space()
        elif action == "packages":
            self.controller._show_packages()
        elif action == "backups":
            self.controller._show_backups()
        elif action == "system_refresh":
            self.controller._refresh_system_status()
            self["status"].setText("Odświeżam diagnostykę...")
        elif action == "restart_gui":
            self.controller._confirm_restart()
        elif action == "settings":
            self.controller.open_settings()
        elif action == "info":
            self.session.open(
                MessageBox,
                item.get("description", "Brak dodatkowych informacji."),
                MessageBox.TYPE_INFO,
                timeout=10,
            )


class HealthScreen(Screen):
    skin = HEALTH_SKIN

    def __init__(self, session, initial_status=None):
        Screen.__init__(self, session)
        self.job = None
        self.closed = False
        self["title"] = Label("Kondycja dekodera")
        self["report"] = Label("")
        self["status"] = Label("Odczytywanie danych...")
        self["hint"] = Label("EXIT: wróć   ZIELONY: odśwież")
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {"cancel": self.close_screen, "green": self.refresh}, -1)
        self.onClose.append(self._on_close)
        if initial_status:
            self._render(initial_status)
        self.refresh()

    def _on_close(self):
        self.closed = True
        if self.job is not None:
            self.job.stop()

    def close_screen(self):
        if self.job is not None and self.job.running:
            self.session.open(MessageBox, "Odczyt jeszcze trwa.", MessageBox.TYPE_INFO, timeout=4)
            return
        self.close()

    def refresh(self):
        if self.job is not None and self.job.running:
            return
        self["status"].setText("Odczytywanie danych systemowych...")
        self.job = AsyncJob(self._finished)
        self.job.start(collect_system_status, settings_dict())

    def _finished(self, result, error):
        self.job = None
        if self.closed:
            return
        if error:
            self["status"].setText("Diagnostyka niedostępna: %s" % error)
            return
        self._render(result)

    def _render(self, data):
        memory = data.get("memory", {})
        flash = data.get("flash", {})
        storage = data.get("storage", {})
        storage_state = "zamontowany" if storage.get("mounted", True) else "NIEZAMONTOWANY"
        self["report"].setText("Model: %s\nObraz: %s  %s  build %s\nArchitektura: %s\nPython: %s\n\nCPU: %d%% (load %.2f, rdzenie %d)\nRAM: %s / %s (%d%%)\nRootFS: %s / %s (%d%%), wolne %s\nMagazyn: %s (%s), wolne %s\nTemperatura: %s\nUptime: %s\nEnigma2: %s   opkg: %s" % (data.get("model", "n/d"), data.get("image", "n/d"), data.get("version", "n/d"), data.get("build", "n/d"), data.get("architecture", "n/d"), data.get("python", "n/d"), data.get("cpu_percent", 0), data.get("load", 0.0), data.get("cpu_count", 0), _format_size(memory.get("used", 0)), _format_size(memory.get("total", 0)), memory.get("percent", 0), _format_size(flash.get("used", 0)), _format_size(flash.get("total", 0)), flash.get("percent", 0), _format_size(flash.get("free", 0)), storage_state, storage.get("path", storage.get("mount", "n/d")), _format_size(storage.get("free", 0)), data.get("temperature", "n/d"), _format_uptime(data.get("uptime", 0)), "uruchomiony" if data.get("enigma2_running") else "niepotwierdzony", "dostępne" if data.get("opkg_available") else "brak"))
        self["status"].setText("Odczyt zakończony: %s" % time.strftime("%H:%M:%S"))
