# -*- coding: utf-8 -*-

"""Konfiguracja pluginu E2-Foorys."""

from __future__ import absolute_import

from Components.config import (
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
RELAY_DEFAULT_URL = "https://raport.forys.pro:9443"
RELAY_CERT_SHA256 = "bfc91e3fa75d5628fd908622e76bc7c92c4ad68f380a76c5e58557dc33c8be88"


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
    if not hasattr(section, "relay_url"):
        section.relay_url = ConfigText(default=RELAY_DEFAULT_URL, fixed_size=False)
    if not hasattr(section, "relay_enabled"):
        section.relay_enabled = ConfigYesNo(default=True)
    if not hasattr(section, "relay_device_name"):
        section.relay_device_name = ConfigText(default="Foorys dekoder", fixed_size=False)
    if not hasattr(section, "relay_pairing_code"):
        section.relay_pairing_code = ConfigPassword(default="", fixed_size=False)
    if not hasattr(section, "relay_device_id"):
        section.relay_device_id = ConfigText(default="", fixed_size=False)
    if not hasattr(section, "relay_device_token"):
        section.relay_device_token = ConfigPassword(default="", fixed_size=False)
    if not hasattr(section, "relay_cert_sha256"):
        section.relay_cert_sha256 = ConfigText(default=RELAY_CERT_SHA256, fixed_size=False)
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
        "relay_url": section.relay_url.value.strip(),
        "relay_enabled": bool(section.relay_enabled.value),
        "relay_device_name": section.relay_device_name.value.strip() or "Foorys dekoder",
        "relay_pairing_code": section.relay_pairing_code.value,
        "relay_device_id": section.relay_device_id.value.strip(),
        "relay_device_token": section.relay_device_token.value,
        "relay_cert_sha256": section.relay_cert_sha256.value.strip().lower(),
    }


def config_entries():
    section = ensure_config()
    return [
        getConfigListEntry("Katalog list kanałów", section.enigma2_dir),
        getConfigListEntry("Ścieżka oscam.dvbapi", section.oscam_dvbapi_path),
        getConfigListEntry("Katalog danych i kopii", section.storage_dir),
        getConfigListEntry("Katalog piconów", section.picon_dir),
        getConfigListEntry("Twórz kopie zapasowe", section.create_backup),
        getConfigListEntry("Pokazuj E2-Foorys w menu głównym", section.show_in_main_menu),
        getConfigListEntry("Adres Foorys Relay", section.relay_url),
        getConfigListEntry("Automatyczne połączenie Relay", section.relay_enabled),
        getConfigListEntry("Nazwa tego dekodera w Relay", section.relay_device_name),
        getConfigListEntry("Kod parowania Relay", section.relay_pairing_code),
    ]


def iptv_config_entries():
    """Pola konfiguracyjne używane wyłącznie przez sekcję Foorys IPTV."""

    section = ensure_config()
    return [
        getConfigListEntry("Link M3U Foorys IPTV (opcjonalny)", section.iptv_m3u_url),
        getConfigListEntry("DNS Foorys IPTV", section.iptv_dns),
        getConfigListEntry("Login Foorys IPTV", section.iptv_username),
        getConfigListEntry("Hasło Foorys IPTV", section.iptv_password),
    ]


def save_config():
    ensure_config()
    configfile.save()
