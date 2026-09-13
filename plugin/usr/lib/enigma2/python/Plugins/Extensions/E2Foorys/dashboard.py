# -*- coding: utf-8 -*-

"""Panel AIO-like E2-Foorys z zakładkami i diagnostyką dekodera."""

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
    install_plugin_package,
    list_backups,
    patch_e2iplayer,
)
from .ui import AsyncJob, CatalogScreen


VERSION = "0.2.2"


MAIN_SKIN = """
<screen name="E2FoorysMain" position="center,center" size="1180,680" title="E2-Foorys" backgroundColor="#06101B" borderWidth="2" borderColor="#1683BB">
    <eLabel position="0,0" size="1180,3" backgroundColor="#1683BB" />
    <eLabel position="20,102" size="1140,1" backgroundColor="#173049" />
    <widget name="logo" position="28,18" size="72,72" alphatest="blend" scale="1" />
    <widget name="title" position="122,20" size="650,38" font="Regular;30" foregroundColor="#F2F7FC" backgroundColor="#0E1C2C" transparent="0" />
    <widget name="subtitle" position="122,61" size="650,27" font="Regular;18" foregroundColor="#8FA7BE" backgroundColor="#0E1C2C" transparent="0" />
    <widget name="version" position="850,14" size="290,22" font="Regular;17" foregroundColor="#28C8F5" backgroundColor="#0E1C2C" transparent="0" horizontalAlignment="right" />
    <widget name="clock" position="850,38" size="290,22" font="Regular;17" foregroundColor="#9DB2C5" backgroundColor="#0E1C2C" transparent="0" horizontalAlignment="right" />
    <widget name="top_stats" position="850,62" size="290,18" font="Regular;14" foregroundColor="#55D6A0" backgroundColor="#0E1C2C" transparent="0" horizontalAlignment="right" />
    <widget name="quick_update" position="850,82" size="290,18" font="Regular;14" foregroundColor="#FFD24A" backgroundColor="#0E1C2C" transparent="0" horizontalAlignment="right" />
    <widget name="section_title" position="35,135" size="470,34" font="Regular;24" foregroundColor="#18C7F5" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="section_count" position="690,138" size="90,28" font="Regular;17" foregroundColor="#7D93A8" backgroundColor="#0C1B2B" transparent="0" horizontalAlignment="right" />
    <widget name="sections" position="28,174" size="235,400" itemHeight="40" font="Regular;19" scrollbarMode="showOnDemand" foregroundColor="#B5C6D6" foregroundColorSelected="#FFFFFF" backgroundColor="#0C1B2B" backgroundColorSelected="#124C6A" transparent="0" />
    <widget name="items" position="302,174" size="480,400" itemHeight="42" font="Regular;19" scrollbarMode="showOnDemand" foregroundColor="#D8E3ED" foregroundColorSelected="#FFFFFF" backgroundColor="#0C1B2B" backgroundColorSelected="#135777" transparent="0" />
    <widget name="info_title" position="830,135" size="305,34" font="Regular;22" foregroundColor="#18C7F5" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="info" position="830,177" size="305,122" font="Regular;17" foregroundColor="#B8C9D8" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="stats_title" position="830,314" size="305,30" font="Regular;20" foregroundColor="#18C7F5" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="stats" position="830,350" size="305,170" font="Regular;17" foregroundColor="#B8C9D8" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="decoder" position="830,532" size="305,38" font="Regular;16" foregroundColor="#55D6A0" backgroundColor="#0C1B2B" transparent="0" />
    <eLabel position="20,600" size="1140,1" backgroundColor="#173049" />
    <widget name="status" position="28,610" size="1125,27" font="Regular;17" foregroundColor="#FFD24A" backgroundColor="#0E1C2C" transparent="0" />
    <widget name="hint" position="28,644" size="1125,25" font="Regular;16" foregroundColor="#71899E" backgroundColor="#0E1C2C" transparent="0" />
</screen>
"""


HEALTH_SKIN = """
<screen name="E2FoorysHealth" position="center,center" size="1000,620" title="E2-Foorys - kondycja dekodera" backgroundColor="#06101B" borderWidth="2" borderColor="#1683BB">
    <widget name="title" position="30,22" size="940,42" font="Regular;28" foregroundColor="#18C7F5" />
    <widget name="report" position="35,85" size="930,445" font="Regular;20" foregroundColor="#D8E3ED" backgroundColor="#0C1B2B" transparent="0" />
    <widget name="status" position="35,545" size="930,30" font="Regular;18" foregroundColor="#FFD24A" />
    <widget name="hint" position="35,580" size="930,25" font="Regular;16" foregroundColor="#71899E" />
</screen>
"""


SECTIONS = (
    ("channels", "Listy kanałów", "Pobieranie i bezpieczna instalacja list kanałów."),
    ("updates", "E2-Foorys / Aktualizacje", "Sprawdzanie manifestu i aktualizacja samego pluginu."),
    ("iptv", "IPTV / Odtwarzacze", "Instalacja E2iPlayera oraz jego patcha."),
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
        self.focus = "items"
        self.section_items = []
        self.manifest_job = None
        self.system_job = None
        self.action_job = None
        self.closed = False
        self.quick_update_requested = False
        self["logo"] = Pixmap()
        self["title"] = Label("E2-Foorys")
        self["subtitle"] = Label("Panel zarządzania Enigma2")
        self["version"] = Label("Foorys v%s" % VERSION)
        self["clock"] = Label("")
        self["section_title"] = Label("Listy kanałów")
        self["section_count"] = Label("1/%d" % len(SECTIONS))
        self["quick_update"] = Label("NIEBIESKI: SZYBKA AKTUALIZACJA")
        self["sections"] = MenuList([(section[1], section[0]) for section in SECTIONS])
        self["items"] = MenuList([])
        self["info_title"] = Label("Listy kanałów")
        self["info"] = Label("Pobieranie i bezpieczna instalacja list kanałów.")
        self["stats_title"] = Label("Stan dekodera")
        self["stats"] = Label("CPU: --   RAM: --\nFlash: --   Dysk: --\nTemperatura: --\nUptime: --")
        self["top_stats"] = Label("CPU: --   RAM: --")
        self["decoder"] = Label("Odczytywanie stanu dekodera...")
        self["status"] = Label("Łączenie z centralną bazą GitHub...")
        self["hint"] = Label("LEWO/PRAWO: zakładka   OK: wybierz   ZIELONY: odśwież   MENU: ustawienia   EXIT: zamknij")
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions", "MenuActions", "ColorActions"],
            {
                "ok": self.select,
                "cancel": self.close_screen,
                "menu": self.open_settings,
                "left": self.focus_left,
                "right": self.focus_right,
                "up": self.move_up,
                "down": self.move_down,
                "pageUp": self.page_up,
                "pageDown": self.page_down,
                "green": self.refresh_all,
                "blue": self.quick_update,
                "info": self.show_health,
            },
            -1,
        )
        self.onClose.append(self._on_close)
        self.onLayoutFinish.append(self._layout_ready)
        self._render_section()
        self._update_focus()
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
        # OpenATV renderuje zawartość MenuList dopiero po utworzeniu instancji
        # GUI; ponowne zasilenie list usuwa pusty ekran przy pierwszym wejściu.
        self._render_section()

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

    def _update_focus(self):
        for name in ("sections", "items"):
            try:
                self[name].instance.setSelectionEnable(1 if name == self.focus else 0)
            except (AttributeError, TypeError):
                pass

    def focus_left(self):
        self.focus = "sections"
        self._update_focus()

    def focus_right(self):
        self.focus = "items"
        self._update_focus()

    @staticmethod
    def _selected_index(widget):
        try:
            value = widget.getSelectedIndex()
            return int(value) if value is not None else -1
        except (AttributeError, TypeError, ValueError):
            return -1

    @staticmethod
    def _move_to_index(widget, index):
        try:
            widget.moveToIndex(index)
        except AttributeError:
            try:
                widget.setIndex(index)
            except AttributeError:
                pass

    def _move(self, method):
        widget = self["sections"] if self.focus == "sections" else self["items"]
        try:
            getattr(widget, method)()
        except AttributeError:
            return
        if self.focus == "sections":
            self.section_index = max(0, min(self._selected_index(widget), len(SECTIONS) - 1))
            self._render_section()
        else:
            self._update_item_info()

    def move_up(self):
        self._move("up")

    def move_down(self):
        self._move("down")

    def page_up(self):
        self._move("pageUp")

    def page_down(self):
        self._move("pageDown")

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
                self._item("Sprawdź wolne miejsce", "Użycie flasha oraz katalogu danych pluginu.", "free_space"),
                self._item("Restart GUI Enigma2", "Restart interfejsu po dodatkowym potwierdzeniu.", "restart_gui"),
                self._item("Ustawienia E2-Foorys", "GitHub, manifest, ścieżki docelowe i kopie bezpieczeństwa.", "settings"),
            ])
        elif section_id == "diagnostics":
            result.extend([
                self._item("Pełna diagnostyka dekodera", "Otwiera szczegółowy raport parametrów systemu.", "health"),
                self._item("Wolne miejsce / magazyn", "Kontroluje flash oraz wskazany dysk HDD/USB.", "free_space"),
                self._item("Zainstalowane pakiety softcam", "Pokazuje znalezione pakiety Oscam, softcam i E2iPlayer.", "packages"),
                self._item("Odśwież dane diagnostyczne", "Ponownie odczytuje parametry bez zmiany konfiguracji.", "system_refresh"),
            ])
        return result

    def _render_section(self):
        section_id, title, description = SECTIONS[self.section_index]
        self.section_items = self._items_for_section(section_id)
        self["section_title"].setText(title)
        self["section_count"].setText("%d/%d" % (self.section_index + 1, len(SECTIONS)))
        self["items"].setList([(item["title"], item["action"]) for item in self.section_items])
        self._move_to_index(self["items"], 0)
        self["info_title"].setText(title)
        self["info"].setText(_short_description(description))
        self._update_item_info()

    def _update_item_info(self):
        index = self._selected_index(self["items"])
        if 0 <= index < len(self.section_items):
            item = self.section_items[index]
            self["info_title"].setText(item.get("title", "E2-Foorys"))
            self["info"].setText(_short_description(item.get("description", "")))

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
            self.manifest = None
            self._render_section()
            self["status"].setText("GitHub/manifest: %s" % error)
            if quick_update_requested:
                self.session.open(MessageBox, "Nie udało się sprawdzić aktualizacji:\n%s" % error, MessageBox.TYPE_ERROR, timeout=10)
            return
        self.manifest = result
        self._render_section()
        self["status"].setText("GitHub OK: %d list, %d pluginów%s%s." % (len(result.get("channel_lists", [])), len(result.get("plugins", [])), ", oscam.dvbapi" if result.get("oscam_dvbapi") else "", ", aktualizacja" if result.get("plugin_update") else ""))
        if quick_update_requested:
            self._quick_update_from_manifest()

    def quick_update(self):
        """Skrót z niebieskiego przycisku: sprawdza i uruchamia aktualizację."""

        if self.action_job is not None and self.action_job.running:
            self["status"].setText("Inna operacja jest jeszcze uruchomiona.")
            return
        self.quick_update_requested = True
        self._refresh_manifest()

    def _quick_update_from_manifest(self):
        update = (self.manifest or {}).get("plugin_update")
        if update and version_is_newer(update.get("version"), VERSION):
            self.session.open(
                CatalogScreen,
                "Szybka aktualizacja E2-Foorys",
                [update],
                install_plugin_package,
            )
            return
        self.session.open(
            MessageBox,
            "E2-Foorys jest aktualny (%s)." % VERSION,
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
            self["stats"].setText("Diagnostyka niedostępna")
            self["decoder"].setText("Nie udało się odczytać stanu")
            return
        self.system_status = result
        self._render_stats(result)

    def _render_stats(self, data):
        memory = data.get("memory", {})
        flash = data.get("flash", {})
        storage = data.get("storage", {})
        self["stats"].setText("CPU: %d%%   RAM: %d%%\nFlash: %d%%  wolne %s\nDysk: %d%%  wolne %s\nTemperatura: %s\nUptime: %s" % (data.get("cpu_percent", 0), memory.get("percent", 0), flash.get("percent", 0), _format_size(flash.get("free", 0)), storage.get("percent", 0), _format_size(storage.get("free", 0)), data.get("temperature", "n/d"), _format_uptime(data.get("uptime", 0))))
        self["top_stats"].setText("CPU: %d%%   RAM: %d%%" % (data.get("cpu_percent", 0), memory.get("percent", 0)))
        self["decoder"].setText("%s | %s | %s" % (data.get("model", "n/d"), data.get("version", "n/d"), "Enigma2 OK" if data.get("enigma2_running") else "Enigma2?"))

    def refresh_all(self):
        self._update_clock()
        self._refresh_system_status()
        self._refresh_manifest()

    def select(self):
        if self.focus == "sections":
            self.focus_right()
            return
        index = self._selected_index(self["items"])
        if not 0 <= index < len(self.section_items):
            return
        item = self.section_items[index]
        action = item.get("action")
        if action == "refresh":
            self._refresh_manifest()
        elif action == "install":
            self.session.open(CatalogScreen, item.get("catalog_title", "E2-Foorys"), [item.get("entry")], item.get("operation"))
        elif action == "health":
            self.show_health()
        elif action == "free_space":
            self._show_free_space()
        elif action == "packages":
            self._show_packages()
        elif action == "backups":
            self._show_backups()
        elif action == "system_refresh":
            self._refresh_system_status()
            self["status"].setText("Odświeżam diagnostykę...")
        elif action == "restart_gui":
            self._confirm_restart()
        elif action == "settings":
            self.open_settings()
        elif action == "info":
            self.session.open(MessageBox, item.get("description", "Brak dodatkowych informacji."), MessageBox.TYPE_INFO, timeout=10)

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
        message = "Flash (%s)\nZajęte: %s / %s (%d%%)\nWolne: %s\n\nMagazyn (%s)\nZajęte: %s / %s (%d%%)\nWolne: %s" % (flash.get("mount", "/"), _format_size(flash.get("used", 0)), _format_size(flash.get("total", 0)), flash.get("percent", 0), _format_size(flash.get("free", 0)), storage.get("mount", "n/d"), _format_size(storage.get("used", 0)), _format_size(storage.get("total", 0)), storage.get("percent", 0), _format_size(storage.get("free", 0)))
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
        self["report"].setText("Model: %s\nObraz: %s  %s  build %s\nArchitektura: %s\nPython: %s\n\nCPU: %d%% (load %.2f, rdzenie %d)\nRAM: %s / %s (%d%%)\nFlash: %s / %s (%d%%), wolne %s\nMagazyn: %s / %s (%d%%), wolne %s\nTemperatura: %s\nUptime: %s\nEnigma2: %s   opkg: %s" % (data.get("model", "n/d"), data.get("image", "n/d"), data.get("version", "n/d"), data.get("build", "n/d"), data.get("architecture", "n/d"), data.get("python", "n/d"), data.get("cpu_percent", 0), data.get("load", 0.0), data.get("cpu_count", 0), _format_size(memory.get("used", 0)), _format_size(memory.get("total", 0)), memory.get("percent", 0), _format_size(flash.get("used", 0)), _format_size(flash.get("total", 0)), flash.get("percent", 0), _format_size(flash.get("free", 0)), _format_size(storage.get("used", 0)), _format_size(storage.get("total", 0)), storage.get("percent", 0), _format_size(storage.get("free", 0)), data.get("temperature", "n/d"), _format_uptime(data.get("uptime", 0)), "uruchomiony" if data.get("enigma2_running") else "niepotwierdzony", "dostępne" if data.get("opkg_available") else "brak"))
        self["status"].setText("Odczyt zakończony: %s" % time.strftime("%H:%M:%S"))
