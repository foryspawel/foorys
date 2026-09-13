# -*- coding: utf-8 -*-

"""Interfejs użytkownika pluginu E2-Foorys."""

from __future__ import absolute_import

import threading
import traceback
import os

from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

try:
    from enigma import eTimer
except ImportError:  # pragma: no cover - tylko podczas pracy poza dekoderem
    eTimer = None

from .config import config_entries, ensure_config, save_config, settings_dict
from .operations import (
    install_e2iplayer,
    fetch_manifest,
    install_channel_list,
    install_oscam_dvbapi,
    install_oscam_stable,
    install_plugin_package,
    patch_e2iplayer,
)


MAIN_SKIN = """
<screen name="E2FoorysMain" position="center,center" size="1180,680" title="E2-Foorys" backgroundColor="#07111D" borderWidth="2" borderColor="#1E789E">
    <widget name="logo" position="25,18" size="76,76" alphatest="blend" scale="1" />
    <widget name="title" position="125,22" size="650,42" font="Regular;32" foregroundColor="#F2F7FC" backgroundColor="#0E1C2C" transparent="0" />
    <widget name="subtitle" position="125,62" size="650,25" font="Regular;18" foregroundColor="#8FA7BE" backgroundColor="#0E1C2C" transparent="0" />
    <widget name="list" position="35,125" size="760,460" itemHeight="46" font="Regular;22" scrollbarMode="showOnDemand" foregroundColor="#D8E3ED" foregroundColorSelected="#FFFFFF" backgroundColor="#0D1A29" transparent="0" />
    <widget name="status" position="35,610" size="1110,28" font="Regular;18" foregroundColor="#FFD24A" backgroundColor="#0E1C2C" transparent="0" />
    <widget name="hint" position="35,645" size="1110,25" font="Regular;16" foregroundColor="#70879D" backgroundColor="#0E1C2C" transparent="0" />
</screen>
"""

CATALOG_SKIN = """
<screen name="E2FoorysCatalog" position="center,center" size="1000,620" title="E2-Foorys">
    <widget name="title" position="30,20" size="940,45" font="Regular;30" />
    <widget name="list" position="30,85" size="940,420" scrollbarMode="showOnDemand" />
    <widget name="status" position="30,525" size="940,35" font="Regular;22" />
    <widget name="hint" position="30,565" size="940,30" font="Regular;18" />
</screen>
"""


class AsyncJob(object):
    """Wykonuje I/O poza głównym wątkiem GUI i wraca przez eTimer."""

    def __init__(self, callback):
        self.callback = callback
        self.thread = None
        self.result = None
        self.error = None
        self.trace = ""
        self.timer = eTimer() if eTimer is not None else None
        if self.timer is not None:
            try:
                self.timer.callback.append(self._poll)
            except AttributeError:
                self.timer.timeout.get().append(self._poll)

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, function, *args):
        if self.running:
            return False

        def runner():
            try:
                self.result = function(*args)
            except Exception as exc:  # noqa: broad-except - błąd pokazujemy użytkownikowi
                self.error = exc
                self.trace = traceback.format_exc()

        self.thread = threading.Thread(target=runner)
        self.thread.daemon = True
        self.thread.start()
        if self.timer is not None:
            self.timer.start(200, True)
        return True

    def _poll(self):
        if self.running:
            self.timer.start(200, True)
            return
        self.callback(self.result, self.error)

    def stop(self):
        if self.timer is not None:
            self.timer.stop()


def _versioned_label(item):
    name = item.get("name", item.get("id", "?"))
    version = item.get("version", "?")
    description = item.get("description", "")
    if description:
        return "%s  [%s] - %s" % (name, version, description)
    return "%s  [%s]" % (name, version)


class E2FoorysMain(Screen):
    skin = MAIN_SKIN

    def __init__(self, session):
        Screen.__init__(self, session)
        ensure_config()
        self.session = session
        self.manifest = None
        self.job = None
        self.closed = False
        self["logo"] = Pixmap()
        self["title"] = Label("E2-Foorys")
        self["subtitle"] = Label("Centrum list kanałów, pluginów i softcamów")
        self["list"] = MenuList([])
        self["status"] = Label("")
        self["hint"] = Label("OK: wybierz   MENU: ustawienia   EXIT: zamknij")
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions", "MenuActions"],
            {
                "ok": self.select,
                "cancel": self.close_screen,
                "menu": self.open_settings,
            },
            -1,
        )
        self.onClose.append(self._on_close)
        self.onLayoutFinish.append(self._layout_ready)
        self._render_menu()
        self._refresh_manifest()

    def _layout_ready(self):
        try:
            path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "foorys.png")
            if self["logo"].instance is not None and os.path.exists(path):
                self["logo"].instance.setPixmapFromFile(path)
                self["logo"].show()
        except Exception:
            pass

    def _on_close(self):
        self.closed = True
        if self.job is not None:
            self.job.stop()

    def close_screen(self):
        if self.job is not None and self.job.running:
            self.session.open(MessageBox, "Operacja jeszcze trwa.", MessageBox.TYPE_INFO, timeout=4)
            return
        self.close()

    def _render_menu(self):
        items = [("Odśwież manifest", "refresh")]
        if self.manifest:
            channels = self.manifest.get("channel_lists", [])
            plugins = self.manifest.get("plugins", [])
            items.append(("Listy kanałów (%d)" % len(channels), "channels"))
            items.append(("Instaluj plugin (%d)" % len(plugins), "plugins"))
            if self.manifest.get("oscam_dvbapi"):
                items.append(("Aktualizuj oscam.dvbapi", "oscam"))
        else:
            items.append(("Listy kanałów - pobierz manifest najpierw", "disabled"))
            items.append(("Pluginy - pobierz manifest najpierw", "disabled"))
        items.extend(
            [
                ("Ustawienia", "settings"),
                ("Informacje", "info"),
            ]
        )
        self["list"].setList(items)

    def _refresh_manifest(self):
        if self.job is not None and self.job.running:
            self["status"].setText("Manifest jest już pobierany...")
            return
        url = settings_dict().get("manifest_url", "")
        if not url:
            self["status"].setText("Ustaw URL manifestu przez MENU, aby pobrać katalog.")
            return
        self["status"].setText("Pobieranie manifestu...")
        self.job = AsyncJob(self._manifest_finished)
        self.job.start(fetch_manifest, url)

    def _manifest_finished(self, result, error):
        self.job = None
        if self.closed:
            return
        if error:
            self.manifest = None
            self._render_menu()
            self["status"].setText("Błąd manifestu: %s" % error)
            return
        self.manifest = result
        self._render_menu()
        self["status"].setText(
            "Manifest OK: %d list, %d pluginów%s."
            % (
                len(result.get("channel_lists", [])),
                len(result.get("plugins", [])),
                ", oscam.dvbapi dostępny" if result.get("oscam_dvbapi") else "",
            )
        )

    def select(self):
        current = self["list"].getCurrent()
        if not current:
            return
        action = current[1]
        if action == "refresh":
            self._refresh_manifest()
        elif action == "channels":
            self.open_catalog("Listy kanałów", self.manifest.get("channel_lists", []), install_channel_list)
        elif action == "plugins":
            self.open_catalog("Instalacja pluginu", self.manifest.get("plugins", []), install_plugin_package)
        elif action == "oscam":
            self.open_catalog("oscam.dvbapi", [self.manifest.get("oscam_dvbapi")], install_oscam_dvbapi)
        elif action == "settings":
            self.open_settings()
        elif action == "info":
            self.session.open(
                MessageBox,
                "E2-Foorys 0.1.1\n\n"
                "Zarządzanie listami kanałów, pakietami IPK/DEB "
                "oraz oscam.dvbapi.\n\n"
                "Każdy plik z repozytorium jest weryfikowany SHA-256.",
                MessageBox.TYPE_INFO,
                timeout=10,
            )

    def open_catalog(self, title, entries, operation):
        self.session.open(CatalogScreen, title, entries, operation)

    def open_settings(self):
        self.session.openWithCallback(self._settings_closed, E2FoorysConfig)

    def _settings_closed(self, _result=None):
        self._render_menu()
        if _result in ("e2iplayer_install", "e2iplayer_patch", "oscam_stable"):
            self._open_system_action(_result)
            return
        if settings_dict().get("manifest_url"):
            self._refresh_manifest()

    def _open_system_action(self, action):
        actions = {
            "e2iplayer_install": (
                "Instalacja E2iPlayer",
                {
                    "id": "e2iplayer",
                    "name": "E2iPlayer",
                    "version": "Python 3 / OE-Mirrors",
                    "description": "Pobiera i uruchamia oficjalny instalator.",
                },
                install_e2iplayer,
            ),
            "e2iplayer_patch": (
                "Patch E2iPlayer",
                {
                    "id": "e2iplayer-patch",
                    "name": "E2iPlayer patch",
                    "version": "hosttorrentyts",
                    "description": "Uruchamia wskazany skrypt patchujący.",
                },
                patch_e2iplayer,
            ),
            "oscam_stable": (
                "Instalacja Oscam stable",
                {
                    "id": "oscam-stable",
                    "name": "Oscam stable",
                    "version": "OEA feed",
                    "description": "Wykonuje feed OEA, opkg update i instalację pakietu.",
                },
                install_oscam_stable,
            ),
        }
        title, entry, operation = actions[action]
        self.open_catalog(title, [entry], operation)


class CatalogScreen(Screen):
    skin = CATALOG_SKIN

    def __init__(self, session, title, entries, operation):
        Screen.__init__(self, session)
        self.session = session
        self.title_text = title
        self.entries = [entry for entry in entries if entry]
        self.operation = operation
        self.job = None
        self.closed = False
        self["title"] = Label(title)
        self["list"] = MenuList([(_versioned_label(entry), entry.get("id", "")) for entry in self.entries])
        self["status"] = Label("Wybierz element i naciśnij OK.")
        self["hint"] = Label("OK: instaluj   EXIT: wróć")
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {"ok": self.confirm, "cancel": self.close_screen},
            -1,
        )
        self.onClose.append(self._on_close)
        if not self.entries:
            self["status"].setText("Brak elementów w tej sekcji manifestu.")

    def _on_close(self):
        self.closed = True
        if self.job is not None:
            self.job.stop()

    def close_screen(self):
        if self.job is not None and self.job.running:
            self.session.open(MessageBox, "Operacja jeszcze trwa.", MessageBox.TYPE_INFO, timeout=4)
            return
        self.close()

    def confirm(self):
        if self.job is not None and self.job.running:
            return
        index = self["list"].getSelectedIndex()
        if index is None or index < 0 or index >= len(self.entries):
            return
        item = self.entries[index]
        question = "Zainstalować '%s' w wersji %s?" % (
            item.get("name", item.get("id", "element")),
            item.get("version", "?"),
        )
        if item.get("description"):
            question += "\n\n%s" % item["description"]
        self.session.openWithCallback(
            lambda answer: self._confirmed(answer, item),
            MessageBox,
            question,
            MessageBox.TYPE_YESNO,
            default=True,
        )

    def _confirmed(self, answer, item):
        if not answer:
            return
        self["status"].setText("Pobieranie i instalacja - proszę czekać...")
        self.job = AsyncJob(self._finished)
        self.job.start(self.operation, item, settings_dict())

    def _finished(self, result, error):
        self.job = None
        if self.closed:
            return
        if error:
            self["status"].setText("Operacja nieudana.")
            self.session.open(
                MessageBox,
                "Nie udało się zakończyć operacji:\n%s" % error,
                MessageBox.TYPE_ERROR,
                timeout=12,
            )
            return
        self["status"].setText("Operacja zakończona pomyślnie.")
        message = self._result_message(result)
        self.session.openWithCallback(
            self._after_success,
            MessageBox,
            message,
            MessageBox.TYPE_YESNO,
            timeout=15,
            default=False,
        )

    def _result_message(self, result):
        kind = result.get("kind")
        if kind == "channels":
            files = ", ".join(result.get("installed", []))
            return "Lista kanałów zainstalowana.\n\nPliki: %s\n\nZrestartować GUI Enigma2?" % files
        if kind == "oscam.dvbapi":
            return "oscam.dvbapi zaktualizowany:\n%s\n\nZrestartować GUI Enigma2?" % result.get("target", "")
        if kind == "e2iplayer":
            return "E2iPlayer został zainstalowany.\n\nZrestartować GUI Enigma2?"
        if kind == "e2iplayer-patch":
            return "Patch E2iPlayer został wykonany.\n\nZrestartować GUI Enigma2?"
        if kind == "oscam-stable":
            return "Oscam stable został zainstalowany.\n\nZrestartować GUI Enigma2?"
        return "Plugin '%s' zainstalowany.\n\nZrestartować GUI Enigma2?" % result.get("name", "plugin")

    def _after_success(self, restart=False):
        if not restart:
            return
        try:
            from Screens.Standby import TryQuitMainloop

            self.session.open(TryQuitMainloop, 3)
        except Exception:
            self.session.open(
                MessageBox,
                "Uruchom ręcznie restart GUI Enigma2.",
                MessageBox.TYPE_INFO,
                timeout=8,
            )


class E2FoorysConfig(Screen, ConfigListScreen):
    skin = """
    <screen name="E2FoorysConfig" position="center,center" size="1000,560" title="E2-Foorys - ustawienia">
        <widget name="config" position="30,35" size="940,430" scrollbarMode="showOnDemand" />
        <widget name="hint" position="30,490" size="940,35" font="Regular;22" />
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        ConfigListScreen.__init__(self, config_entries(), session=session)
        self["hint"] = Label("OK: edytuj   ZIELONY: zapisz   EXIT: anuluj")
        self["actions"] = ActionMap(
            ["SetupActions", "ColorActions"],
            {
                "ok": self.keyOK,
                "save": self.keySave,
                "green": self.keySave,
                "cancel": self.keyCancel,
            },
            -2,
        )

    def keySave(self):
        system_action = ensure_config().system_action
        action = system_action.value
        system_action.setValue("none")
        for _label, element in self["config"].list:
            element.save()
        save_config()
        self.close(action)

    def keyCancel(self):
        for _label, element in self["config"].list:
            element.cancel()
        self.close(False)
