# -*- coding: utf-8 -*-

"""Operacje sieciowe i instalacyjne pluginu E2-Foorys."""

from __future__ import absolute_import

import json
import os
import re
import shutil
import subprocess
import tempfile
import time

try:
    from urllib.parse import urljoin, urlparse
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover - ścieżka dla bardzo starych obrazów E2
    from urllib2 import Request, urlopen
    from urlparse import urljoin, urlparse

from .core import (
    ArchiveError,
    atomic_copy,
    extract_archive,
    find_channel_files,
    is_channel_file_name,
    normalize_manifest,
    parse_manifest,
    sha256_file,
    verify_sha256,
)


class OperationError(RuntimeError):
    """Operacja nie mogła zostać ukończona."""


USER_AGENT = "E2-Foorys/0.1 Enigma2"
MANIFEST_LIMIT = 4 * 1024 * 1024
DOWNLOAD_LIMIT = 512 * 1024 * 1024

# Akcje systemowe są stałe i nie są pobierane z manifestu. Każda z nich jest
# uruchamiana dopiero po potwierdzeniu w GUI pluginu.
E2IPLAYER_INSTALL_COMMAND = (
    'wget -q "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/'
    'refs/heads/python3/e2iplayer_install.sh" -O - | /bin/sh'
)
E2IPLAYER_PATCH_COMMAND = (
    'wget -q "--no-check-certificate" '
    'https://github.com/popking159/mye2iplayer/raw/main/update_e2iplayer_patch.sh '
    '-O - | /bin/sh'
)
OSCAM_STABLE_COMMAND = (
    'wget -O - -q "http://updates.mynonpublic.com/oea/feed" | bash '
    '&& opkg update && opkg install enigma2-plugin-softcams-oscam-stable'
)


def _setting(settings, key, default=""):
    value = settings.get(key, default) if settings else default
    if isinstance(value, str):
        value = value.strip()
        return value or default
    return value


def _ensure_absolute_directory(path, label):
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            raise OperationError("Nie można utworzyć %s: %s" % (label, exc))
    return path


def _validate_download_url(url):
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https", "file"):
        raise OperationError("Do pobierania dozwolone są wyłącznie URL-e HTTP(S) lub file://.")


def _read_response(response, limit):
    content = bytearray()
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > limit:
            raise OperationError("Pobrany plik przekracza limit %d MB." % (limit // (1024 * 1024)))
    return bytes(content)


def fetch_manifest(manifest_url):
    """Pobiera i waliduje manifest, rozwijając względne URL-e."""

    _validate_download_url(manifest_url)
    request = Request(manifest_url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=25) as response:
            raw = _read_response(response, MANIFEST_LIMIT)
    except Exception as exc:
        raise OperationError("Nie można pobrać manifestu: %s" % exc)

    manifest = parse_manifest(raw)
    for collection_name in ("channel_lists", "plugins"):
        for item in manifest[collection_name]:
            item["url"] = urljoin(manifest_url, item["url"])
            _validate_download_url(item["url"])
    if manifest.get("oscam_dvbapi"):
        manifest["oscam_dvbapi"]["url"] = urljoin(
            manifest_url, manifest["oscam_dvbapi"]["url"]
        )
        _validate_download_url(manifest["oscam_dvbapi"]["url"])
    return normalize_manifest(manifest)


def _safe_filename(value, fallback="package"):
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or ""))
    value = value.strip("._")
    return value or fallback


def download_verified(url, destination, expected_sha256, max_bytes=DOWNLOAD_LIMIT):
    """Pobiera plik do .part, sprawdza SHA-256 i atomowo zmienia nazwę."""

    _validate_download_url(url)
    expected_sha256 = str(expected_sha256).lower()
    parent = os.path.dirname(os.path.abspath(destination))
    os.makedirs(parent, exist_ok=True)
    temporary = destination + ".part"
    if os.path.exists(temporary):
        os.unlink(temporary)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    received = 0
    try:
        with urlopen(request, timeout=60) as response, open(temporary, "wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > max_bytes:
                    raise OperationError("Pobrany plik przekracza dozwolony limit.")
                output.write(chunk)
        if not verify_sha256(temporary, expected_sha256):
            actual = sha256_file(temporary)
            raise OperationError(
                "Nieprawidłowa suma SHA-256. Oczekiwano %s, otrzymano %s."
                % (expected_sha256, actual)
            )
        os.replace(temporary, destination)
    except OperationError:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    except Exception as exc:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise OperationError("Pobieranie nie powiodło się: %s" % exc)
    return destination


def _timestamp():
    return time.strftime("%Y%m%d-%H%M%S")


def _backup_existing(source, backup_root, metadata):
    if not os.path.isfile(source):
        return None
    os.makedirs(backup_root, exist_ok=True)
    target = os.path.join(backup_root, os.path.basename(source))
    shutil.copy2(source, target)
    metadata.append({"source": source, "backup": target, "name": os.path.basename(source)})
    return target


def _write_json(path, data):
    temporary = path + ".part"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def install_channel_list(item, settings):
    """Pobiera archiwum listy kanałów i instaluje tylko znane pliki E2."""

    storage = _ensure_absolute_directory(
        _setting(settings, "storage_dir", "/media/hdd/e2foorys"),
        "katalog danych",
    )
    destination = _ensure_absolute_directory(
        _setting(settings, "enigma2_dir", "/etc/enigma2"),
        "katalog Enigma2",
    )
    cache = _ensure_absolute_directory(os.path.join(storage, "cache"), "cache")
    archive_extension = ".zip" if urlparse(item["url"]).path.lower().endswith(".zip") else ".tar"
    archive_name = "channels-%s-%s%s" % (
        _safe_filename(item.get("id")),
        _safe_filename(item.get("version")),
        archive_extension,
    )
    archive_path = os.path.join(cache, archive_name)
    download_verified(item["url"], archive_path, item["sha256"])

    staging = tempfile.mkdtemp(prefix="e2foorys-channels-", dir=storage)
    backup_metadata = []
    installed = []
    try:
        try:
            extract_archive(archive_path, staging)
        except ArchiveError as exc:
            raise OperationError("Archiwum listy kanałów jest nieprawidłowe: %s" % exc)
        source_files = find_channel_files(staging)
        if not source_files:
            raise OperationError("Archiwum nie zawiera rozpoznanych plików listy kanałów.")

        backup_root = os.path.join(storage, "backups", "channels-%s" % _timestamp())
        create_backup = bool(_setting(settings, "create_backup", True))
        seen_names = set()
        for source in source_files:
            filename = os.path.basename(source)
            if not is_channel_file_name(filename):
                continue
            if filename in seen_names:
                raise OperationError(
                    "Archiwum zawiera dwa pliki o tej samej nazwie: %s" % filename
                )
            seen_names.add(filename)
            target = os.path.join(destination, filename)
            if create_backup:
                _backup_existing(target, backup_root, backup_metadata)
            atomic_copy(source, target)
            installed.append(filename)

        if backup_metadata:
            _write_json(
                os.path.join(backup_root, "backup.json"),
                {"type": "channels", "created_at": _timestamp(), "files": backup_metadata},
            )
        return {
            "kind": "channels",
            "version": item.get("version", ""),
            "installed": installed,
            "backup": backup_root if backup_metadata else None,
        }
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def install_oscam_dvbapi(item, settings):
    """Pobiera oscam.dvbapi i podmienia go atomowo po wykonaniu kopii."""

    storage = _ensure_absolute_directory(
        _setting(settings, "storage_dir", "/media/hdd/e2foorys"),
        "katalog danych",
    )
    target = os.path.abspath(
        _setting(
            settings,
            "oscam_dvbapi_path",
            "/etc/tuxbox/config/oscam-emu/oscam.dvbapi",
        )
    )
    cache = _ensure_absolute_directory(os.path.join(storage, "cache"), "cache")
    downloaded = os.path.join(
        cache,
        "oscam-dvbapi-%s" % _safe_filename(item.get("version"), "latest"),
    )
    download_verified(item["url"], downloaded, item["sha256"], max_bytes=16 * 1024 * 1024)

    backup_metadata = []
    backup_root = os.path.join(storage, "backups", "oscam-%s" % _timestamp())
    if bool(_setting(settings, "create_backup", True)):
        _backup_existing(target, backup_root, backup_metadata)
    atomic_copy(downloaded, target)
    if backup_metadata:
        _write_json(
            os.path.join(backup_root, "backup.json"),
            {"type": "oscam.dvbapi", "created_at": _timestamp(), "files": backup_metadata},
        )
    return {
        "kind": "oscam.dvbapi",
        "target": target,
        "version": item.get("version", ""),
        "backup": backup_root if backup_metadata else None,
    }


def _run_opkg(package_path, timeout=600):
    executable = shutil.which("opkg") or "/usr/bin/opkg"
    if not os.path.exists(executable):
        raise OperationError("Nie znaleziono programu opkg na dekoderze.")
    try:
        process = subprocess.Popen(
            [executable, "install", package_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        output, _unused = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise OperationError("Instalacja pakietu opkg przekroczyła limit czasu.")
    except OSError as exc:
        raise OperationError("Nie można uruchomić opkg: %s" % exc)
    if process.returncode != 0:
        raise OperationError(
            "opkg zakończył się kodem %s:\n%s" % (process.returncode, output[-3000:])
        )
    return output[-3000:]


def _run_shell_command(command, timeout=900):
    """Uruchamia wyłącznie stałą akcję pluginu przez powłokę dekodera."""

    if not isinstance(command, str) or not command.strip():
        raise OperationError("Pusta komenda instalacyjna.")
    if not os.path.exists("/bin/sh"):
        raise OperationError("Na dekoderze brakuje /bin/sh.")
    try:
        process = subprocess.Popen(
            ["/bin/sh", "-c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        output, _unused = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise OperationError("Instalator przekroczył limit czasu.")
    except OSError as exc:
        raise OperationError("Nie można uruchomić instalatora: %s" % exc)
    if process.returncode != 0:
        raise OperationError(
            "Instalator zakończył się kodem %s:\n%s"
            % (process.returncode, output[-3000:])
        )
    return output[-3000:]


def install_e2iplayer(_item, _settings):
    """Instaluje bieżącą gałąź Python 3 E2iPlayer z OE-Mirrors."""

    output = _run_shell_command(E2IPLAYER_INSTALL_COMMAND)
    return {"kind": "e2iplayer", "name": "E2iPlayer", "output": output}


def patch_e2iplayer(_item, _settings):
    """Nakłada patch hosttorrentyts na zainstalowany E2iPlayer."""

    output = _run_shell_command(E2IPLAYER_PATCH_COMMAND)
    return {"kind": "e2iplayer-patch", "name": "E2iPlayer patch", "output": output}


def install_oscam_stable(_item, _settings):
    """Instaluje oscam-stable z feedu OEA zgodnie z komendą użytkownika."""

    output = _run_shell_command(OSCAM_STABLE_COMMAND)
    return {
        "kind": "oscam-stable",
        "name": "Oscam stable",
        "package": "enigma2-plugin-softcams-oscam-stable",
        "output": output,
    }


def install_plugin_package(item, settings):
    """Pobiera i instaluje pakiet .ipk przez opkg."""

    package_type = str(item.get("package_type", "ipk")).lower()
    if package_type not in ("ipk", "deb"):
        raise OperationError("Nieobsługiwany typ pakietu: %s" % package_type)
    storage = _ensure_absolute_directory(
        _setting(settings, "storage_dir", "/media/hdd/e2foorys"),
        "katalog danych",
    )
    packages = _ensure_absolute_directory(os.path.join(storage, "packages"), "pakiety")
    extension = "." + package_type
    filename = "%s-%s%s" % (
        _safe_filename(item.get("id")),
        _safe_filename(item.get("version")),
        extension,
    )
    package_path = os.path.join(packages, filename)
    download_verified(item["url"], package_path, item["sha256"])
    output = _run_opkg(package_path)
    return {
        "kind": "plugin",
        "name": item.get("name", item.get("id", "")),
        "version": item.get("version", ""),
        "package": package_path,
        "output": output,
    }
