# -*- coding: utf-8 -*-

"""Operacje sieciowe i instalacyjne pluginu E2-Foorys."""

from __future__ import absolute_import

import json
import os
import platform
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

FOORYS_OSCAM_DVBAPI_LINES = (
    "P:1884",
    "P:0B01",
    "P:1861",
)


def _setting(settings, key, default=""):
    value = settings.get(key, default) if settings else default
    if isinstance(value, str):
        value = value.strip()
        return value or default
    return value


def _read_text_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read().strip()
    except (OSError, IOError):
        return ""


def _parse_key_value_file(path):
    values = {}
    content = _read_text_file(path)
    for line in content.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def _filesystem_usage(path):
    """Zwraca użycie systemu plików bez uruchamiania zewnętrznych komend."""

    requested = os.path.abspath(str(path or "/"))
    candidate = requested
    while not os.path.exists(candidate) and candidate != os.path.dirname(candidate):
        candidate = os.path.dirname(candidate)
    try:
        stats = os.statvfs(candidate)
        block_size = int(stats.f_frsize or stats.f_bsize or 4096)
        total = int(stats.f_blocks) * block_size
        free = int(stats.f_bavail) * block_size
        used = max(total - free, 0)
        percent = int(round((used * 100.0) / total)) if total else 0
        return {
            "path": requested,
            "mount": candidate,
            "total": total,
            "free": free,
            "used": used,
            "percent": min(max(percent, 0), 100),
        }
    except (OSError, IOError, AttributeError):
        return {
            "path": requested,
            "mount": candidate,
            "total": 0,
            "free": 0,
            "used": 0,
            "percent": 0,
            "error": "brak danych",
        }


def _memory_usage():
    values = {}
    for line in _read_text_file("/proc/meminfo").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            try:
                values[parts[0].rstrip(":")] = int(parts[1]) * 1024
            except ValueError:
                continue
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable")
    if available is None:
        available = sum(values.get(key, 0) for key in ("MemFree", "Buffers", "Cached"))
    used = max(total - available, 0)
    percent = int(round((used * 100.0) / total)) if total else 0
    return {
        "total": total,
        "free": max(available, 0),
        "used": used,
        "percent": min(max(percent, 0), 100),
    }


def _uptime_seconds():
    content = _read_text_file("/proc/uptime").split()
    try:
        return int(float(content[0])) if content else 0
    except (TypeError, ValueError):
        return 0


def _temperature():
    for path in (
        "/proc/stb/sensors/temp0/value",
        "/proc/stb/fp/temp_sensor",
        "/sys/class/thermal/thermal_zone0/temp",
    ):
        value = _read_text_file(path)
        if not value:
            continue
        try:
            number = int(value, 0)
            if number > 1000:
                number = int(round(number / 1000.0))
            return "%d C" % number
        except ValueError:
            return value
    return "n/d"


def _process_running(name):
    executable = shutil.which("pidof") or "/bin/pidof"
    if not os.path.exists(executable):
        return None
    try:
        process = subprocess.Popen(
            [executable, name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output, _unused = process.communicate(timeout=5)
        return process.returncode == 0 and bool(output.strip())
    except (OSError, subprocess.SubprocessError):
        return None


def collect_system_status(settings=None):
    """Zbiera informacje diagnostyczne dekodera tylko w trybie odczytu."""

    settings = settings or {}
    image = _parse_key_value_file("/etc/image-version")
    issue = _read_text_file("/etc/issue").splitlines()
    load_content = _read_text_file("/proc/loadavg").split()
    try:
        load = float(load_content[0]) if load_content else 0.0
    except ValueError:
        load = 0.0
    cpu_count_function = getattr(os, "cpu_count", None)
    cpu_count = cpu_count_function() if cpu_count_function else 1
    cpu_count = max(int(cpu_count or 1), 1)
    cpu_percent = min(max(int(round(load * 100.0 / cpu_count)), 0), 100)
    memory = _memory_usage()
    flash = _filesystem_usage("/")
    storage = _filesystem_usage(_setting(settings, "storage_dir", "/media/hdd"))
    return {
        "model": image.get("machine_name", image.get("box_type", "n/d")),
        "image": image.get("distro", "") or (issue[0] if issue else "n/d"),
        "version": image.get("version", "n/d"),
        "build": image.get("build", "n/d"),
        "architecture": image.get("arch", platform.machine() or "n/d"),
        "python": platform.python_version(),
        "uptime": _uptime_seconds(),
        "load": load,
        "cpu_percent": cpu_percent,
        "cpu_count": cpu_count,
        "memory": memory,
        "flash": flash,
        "storage": storage,
        "temperature": _temperature(),
        "enigma2_running": _process_running("enigma2"),
        "opkg_available": bool(shutil.which("opkg") or os.path.exists("/usr/bin/opkg")),
    }


def collect_installed_packages(_settings=None):
    """Zwraca pakiety związane z E2iPlayerem i softcamami (tylko odczyt)."""

    executable = shutil.which("opkg") or "/usr/bin/opkg"
    if not os.path.exists(executable):
        return {"available": False, "packages": []}
    try:
        process = subprocess.Popen(
            [executable, "list-installed"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        output, _unused = process.communicate(timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise OperationError("Nie można odczytać listy pakietów: %s" % exc)
    if process.returncode != 0:
        raise OperationError("opkg list-installed zakończył się kodem %s." % process.returncode)
    packages = []
    for line in output.splitlines():
        lowered = line.lower()
        if any(token in lowered for token in ("e2iplayer", "oscam", "softcam", "camd")):
            packages.append(line.strip())
    return {"available": True, "packages": packages}


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
    for single_item_name in ("oscam_dvbapi", "plugin_update"):
        if manifest.get(single_item_name):
            manifest[single_item_name]["url"] = urljoin(
                manifest_url, manifest[single_item_name]["url"]
            )
            _validate_download_url(manifest[single_item_name]["url"])
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


def install_current_oscam_dvbapi(_item, settings):
    """Zapisuje aktualny profil Foorys z dokładnie trzema regułami P:."""

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
    backup_metadata = []
    backup_root = os.path.join(storage, "backups", "oscam-%s" % _timestamp())
    if bool(_setting(settings, "create_backup", True)):
        _backup_existing(target, backup_root, backup_metadata)

    temporary = os.path.join(storage, ".foorys-oscam.dvbapi.part")
    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write("\n".join(FOORYS_OSCAM_DVBAPI_LINES) + "\n")
        atomic_copy(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

    if backup_metadata:
        _write_json(
            os.path.join(backup_root, "backup.json"),
            {"type": "oscam.dvbapi", "created_at": _timestamp(), "files": backup_metadata},
        )
    return {
        "kind": "oscam.dvbapi",
        "target": target,
        "version": "foorys-current",
        "lines": list(FOORYS_OSCAM_DVBAPI_LINES),
        "backup": backup_root if backup_metadata else None,
    }


def list_backups(settings=None):
    """Zwraca krótką listę kopii zapisanych przez plugin."""

    root = os.path.join(
        os.path.abspath(_setting(settings or {}, "storage_dir", "/media/hdd/e2foorys")),
        "backups",
    )
    result = []
    if not os.path.isdir(root):
        return {"root": root, "backups": result}
    for name in sorted(os.listdir(root), reverse=True):
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        metadata = _parse_key_value_file(os.path.join(path, "backup.ini"))
        backup_json = os.path.join(path, "backup.json")
        backup_type = "backup"
        if os.path.isfile(backup_json):
            try:
                with open(backup_json, "r", encoding="utf-8") as handle:
                    backup_type = json.load(handle).get("type", backup_type)
            except (OSError, IOError, TypeError, ValueError):
                pass
        result.append({"name": name, "path": path, "type": metadata.get("type", backup_type)})
    return {"root": root, "backups": result}


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
