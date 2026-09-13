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


def ensure_config():
    if not hasattr(config.plugins, "e2foorys"):
        config.plugins.e2foorys = ConfigSubsection()
    section = config.plugins.e2foorys
    if not hasattr(section, "manifest_url"):
        section.manifest_url = ConfigText(default="", fixed_size=False)
    if not hasattr(section, "github_repo"):
        section.github_repo = ConfigText(default="foryspawel/foorys", fixed_size=False)
    if not hasattr(section, "github_branch"):
        section.github_branch = ConfigText(default="main", fixed_size=False)
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
    if not hasattr(section, "create_backup"):
        section.create_backup = ConfigYesNo(default=True)
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
        "manifest_url": section.manifest_url.value.strip(),
        "github_repo": section.github_repo.value.strip(),
        "github_branch": section.github_branch.value.strip(),
        "enigma2_dir": section.enigma2_dir.value.strip(),
        "oscam_dvbapi_path": section.oscam_dvbapi_path.value.strip(),
        "storage_dir": section.storage_dir.value.strip(),
        "create_backup": bool(section.create_backup.value),
    }


def config_entries():
    section = ensure_config()
    return [
        getConfigListEntry("Repozytorium GitHub (owner/repo)", section.github_repo),
        getConfigListEntry("Gałąź GitHub", section.github_branch),
        getConfigListEntry("Własny URL manifestu (puste = GitHub)", section.manifest_url),
        getConfigListEntry("Katalog list kanałów", section.enigma2_dir),
        getConfigListEntry("Ścieżka oscam.dvbapi", section.oscam_dvbapi_path),
        getConfigListEntry("Katalog danych i kopii", section.storage_dir),
        getConfigListEntry("Twórz kopie zapasowe", section.create_backup),
        getConfigListEntry("Akcja instalacyjna", section.system_action),
    ]


def save_config():
    ensure_config()
    configfile.save()
