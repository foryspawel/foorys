# -*- coding: utf-8 -*-

"""Konfiguracja pluginu E2-Foorys."""

from __future__ import absolute_import

from Components.config import (
    ConfigSelection,
    ConfigText,
    ConfigYesNo,
    ConfigSubsection,
    config,
    configfile,
    getConfigListEntry,
)

try:
    from Components.config import ConfigPassword
except ImportError:  # pragma: no cover - starsze obrazy Enigma2
    ConfigPassword = ConfigText


# Centralna baza pluginu. Nie jest edytowalna z poziomu dekodera — wpisy,
# listy kanałów i pakiety są zarządzane wyłącznie w repozytorium właściciela.
CENTRAL_GITHUB_REPOSITORY = "foryspawel/foorys"
CENTRAL_GITHUB_BRANCH = "main"
IPTV_FORYS_DNS = "iptv.forys.pro"


def central_manifest_url():
    # Ten adres jest odświeżany poprawnie po publikacji nowego commita, w
    # przeciwieństwie do cache raw.githubusercontent.com na części obrazów E2.
    return "https://github.com/%s/raw/refs/heads/%s/manifest.json" % (
        CENTRAL_GITHUB_REPOSITORY,
        CENTRAL_GITHUB_BRANCH,
    )


def ensure_config():
    if not hasattr(config.plugins, "e2foorys"):
        config.plugins.e2foorys = ConfigSubsection()
    section = config.plugins.e2foorys
    if not hasattr(section, "manifest_url"):
        section.manifest_url = ConfigText(default="", fixed_size=False)
    # Stare pola github_repo/github_branch mogą pozostać w zapisanej
    # konfiguracji po aktualizacji, ale nie są już używane ani pokazywane.
    if not hasattr(section, "enigma2_dir"):
        section.enigma2_dir = ConfigText(default="/etc/enigma2", fixed_size=False)
    if not hasattr(section, "oscam_dvbapi_path"):
        section.oscam_dvbapi_path = ConfigText(
            default="/etc/tuxbox/config/oscam-emu/oscam.dvbapi", fixed_size=False
        )
    if not hasattr(section, "storage_dir"):
        section.storage_dir = ConfigText(
            default="/media/hdd/e2foorys", fixed_size=False
        )
    if not hasattr(section, "picon_dir"):
        section.picon_dir = ConfigText(
            default="/usr/share/enigma2/picon", fixed_size=False
        )
    if not hasattr(section, "iptv_m3u_url"):
        section.iptv_m3u_url = ConfigText(default="", fixed_size=False)
    if not hasattr(section, "iptv_dns"):
        section.iptv_dns = ConfigText(default=IPTV_FORYS_DNS, fixed_size=False)
    if not hasattr(section, "iptv_username"):
        section.iptv_username = ConfigText(default="", fixed_size=False)
    if not hasattr(section, "iptv_password"):
        section.iptv_password = ConfigPassword(default="", fixed_size=False)
    if not hasattr(section, "create_backup"):
        section.create_backup = ConfigYesNo(default=True)
    if not hasattr(section, "show_in_main_menu"):
        section.show_in_main_menu = ConfigYesNo(default=True)
    if not hasattr(section, "system_action"):
        section.system_action = ConfigSelection(
            default="none",
            choices=[
                ("none", "-- brak akcji --"),
                ("e2iplayer_install", "Instaluj E2iPlayer (Python 3)"),
                ("e2iplayer_patch", "Patch E2iPlayer (hosttorrentyts)"),
                ("oscam_stable", "Instaluj Oscam stable"),
            ],
        )
    return section


def settings_dict():
    section = ensure_config()
    return {
        "manifest_url": central_manifest_url(),
        "github_repo": CENTRAL_GITHUB_REPOSITORY,
        "github_branch": CENTRAL_GITHUB_BRANCH,
        "enigma2_dir": section.enigma2_dir.value.strip(),
        "oscam_dvbapi_path": section.oscam_dvbapi_path.value.strip(),
        "storage_dir": section.storage_dir.value.strip(),
        "picon_dir": section.picon_dir.value.strip(),
        # Dane IPTV są odczytywane tylko lokalnie na dekoderze. Nie są częścią
        # manifestu GitHub ani żadnego pliku publikowanego w repozytorium.
        "iptv_m3u_url": section.iptv_m3u_url.value.strip(),
        "iptv_dns": section.iptv_dns.value.strip() or IPTV_FORYS_DNS,
        "iptv_username": section.iptv_username.value.strip(),
        "iptv_password": section.iptv_password.value,
        "create_backup": bool(section.create_backup.value),
        "show_in_main_menu": bool(section.show_in_main_menu.value),
    }


def config_entries():
    section = ensure_config()
    return [
        getConfigListEntry("Katalog list kanałów", section.enigma2_dir),
        getConfigListEntry("Ścieżka oscam.dvbapi", section.oscam_dvbapi_path),
        getConfigListEntry("Katalog danych i kopii", section.storage_dir),
        getConfigListEntry("Katalog piconów", section.picon_dir),
        getConfigListEntry("Link M3U Foorys IPTV (opcjonalny)", section.iptv_m3u_url),
        getConfigListEntry("DNS Foorys IPTV", section.iptv_dns),
        getConfigListEntry("Login Foorys IPTV", section.iptv_username),
        getConfigListEntry("Hasło Foorys IPTV", section.iptv_password),
        getConfigListEntry("Twórz kopie zapasowe", section.create_backup),
        getConfigListEntry("Pokazuj E2-Foorys w menu głównym", section.show_in_main_menu),
        getConfigListEntry("Akcja instalacyjna", section.system_action),
    ]


def save_config():
    ensure_config()
    configfile.save()
