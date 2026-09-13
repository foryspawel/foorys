# -*- coding: utf-8 -*-

"""Operacje sieciowe i instalacyjne pluginu E2-Foorys."""

from __future__ import absolute_import

import json
import hashlib
import glob
import os
import platform
import re
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import time

try:
    from urllib.parse import quote, urlencode, urljoin, urlparse
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover - ścieżka dla bardzo starych obrazów E2
    from urllib import quote, urlencode
    from urllib2 import Request, urlopen
    from urlparse import urljoin, urlparse

from .core import (
    ArchiveError,
    atomic_copy,
    extract_archive,
    find_channel_files,
    find_picon_files,
    is_channel_file_name,
    normalize_manifest,
    parse_manifest,
    sha256_file,
    verify_sha256,
)
from .compat import (
    binary_type,
    ensure_dir,
    is_path_within,
    open_text,
    replace_file,
    string_types,
    to_text,
    which,
)


class OperationError(RuntimeError):
    """Operacja nie mogła zostać ukończona."""


USER_AGENT = "E2-Foorys/0.8.0 Enigma2"
MANIFEST_LIMIT = 4 * 1024 * 1024
DOWNLOAD_LIMIT = 512 * 1024 * 1024
STORAGE_FALLBACK_DIR = "/etc/enigma2/e2foorys"
MIN_STORAGE_FREE = 4 * 1024 * 1024

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

PUBLIC_SOFTCAM_PACKAGES = {
    "oscam-emu": {
        "name": "OSCam-emu",
        "package": "enigma2-plugin-softcams-oscam-emu",
    },
    "ncam": {
        "name": "NCam",
        "package": "enigma2-plugin-softcams-ncam",
    },
    "cccam-2.3.9": {
        "name": "CCcam 2.3.9",
        "package": "enigma2-plugin-softcams-cccam-2.3.9",
    },
}

FOORYS_OSCAM_DVBAPI_LINES = (
    "P:1884",
    "P:0B01",
    "P:1861",
)

IPTV_FORYS_DNS = "iptv.forys.pro"
IPTV_FORYS_PORT = 8880
IPTV_BOUQUET_NAME = "Foorys IPTV"
IPTV_BOUQUET_FILENAME = "userbouquet.foorys-iptv.tv"
IPTV_MAX_CHANNELS = 10000
IPTV_MAX_PICONS = 1500
IPTV_MAX_PICON_BYTES = 2 * 1024 * 1024

_IPTV_ATTRIBUTE_RE = re.compile(
    r'''([A-Za-z0-9_-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s,]+))'''
)


def _setting(settings, key, default=""):
    value = settings.get(key, default) if settings else default
    if isinstance(value, string_types):
        value = value.strip()
        return value or default
    return value


def _progress(callback, message):
    if callback is None:
        return
    try:
        callback(message)
    except Exception:
        pass


def _read_text_file(path):
    try:
        with open_text(path, "r", errors="replace") as handle:
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


def _mountpoint_for(path):
    """Zwraca najdłuższy punkt montowania obejmujący wskazaną ścieżkę."""

    requested = os.path.abspath(to_text(path or "/"))
    best = "/"
    mounts = _read_text_file("/proc/mounts")
    for line in mounts.splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        mount = fields[1].replace("\\040", " ").replace("\\011", "\t")
        mount = os.path.normpath(mount)
        if requested == mount or requested.startswith(mount.rstrip("/") + "/"):
            if len(mount) > len(best):
                best = mount
    if mounts:
        return best

    candidate = requested
    while candidate != os.path.dirname(candidate):
        if os.path.ismount(candidate):
            return candidate
        candidate = os.path.dirname(candidate)
    return "/" if os.path.ismount("/") else best


def _expected_media_mount(path, mountpoint):
    """Sprawdza, czy /media/hdd lub /media/usb ma własne montowanie."""

    normalized = os.path.normpath(os.path.abspath(to_text(path or "/")))
    if not normalized.startswith("/media/"):
        return True
    parts = normalized.split(os.sep)
    if len(parts) < 3 or not parts[2]:
        return True
    device_root = os.path.join("/media", parts[2])
    return mountpoint == device_root or mountpoint.startswith(device_root + "/")


def _filesystem_usage(path):
    """Zwraca użycie systemu plików bez uruchamiania zewnętrznych komend."""

    requested = os.path.abspath(to_text(path or "/"))
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
            "mountpoint": _mountpoint_for(candidate),
            "mounted": _expected_media_mount(requested, _mountpoint_for(candidate)),
            "fallback": candidate != requested,
            "path_exists": os.path.exists(requested),
            "total": total,
            "free": free,
            "used": used,
            "percent": min(max(percent, 0), 100),
        }
    except (OSError, IOError, AttributeError, NotImplementedError):
        # Python na Windows nie udostępnia statvfs. Fallback jest potrzebny
        # również dla lokalnych testów i podglądu, ale ścieżka dekodera nadal
        # korzysta z dokładnego pomiaru systemu plików Enigma2.
        try:
            disk_usage = getattr(shutil, "disk_usage", None)
            if disk_usage is None:
                raise AttributeError("disk_usage")
            usage = disk_usage(candidate)
            total = int(usage.total)
            free = int(usage.free)
            used = max(total - free, 0)
            percent = int(round((used * 100.0) / total)) if total else 0
            return {
                "path": requested,
                "mount": candidate,
                "mountpoint": _mountpoint_for(candidate),
                "mounted": _expected_media_mount(requested, _mountpoint_for(candidate)),
                "fallback": candidate != requested,
                "path_exists": os.path.exists(requested),
                "total": total,
                "free": free,
                "used": used,
                "percent": min(max(percent, 0), 100),
            }
        except (OSError, IOError, AttributeError):
            return {
                "path": requested,
                "mount": candidate,
                "mountpoint": _mountpoint_for(candidate),
                "mounted": False,
                "fallback": candidate != requested,
                "path_exists": os.path.exists(requested),
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


def _cpu_counters():
    """Czyta sumaryczne liczniki CPU z /proc/stat."""

    content = _read_text_file("/proc/stat")
    for line in content.splitlines():
        if not line.startswith("cpu "):
            continue
        try:
            values = [int(value) for value in line.split()[1:]]
        except (TypeError, ValueError):
            return None
        if len(values) < 4:
            return None
        total = sum(values[:8])
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return total, idle
    return None


def _cpu_usage(interval=0.25):
    """Zwraca rzeczywiste zajęcie CPU z różnicy dwóch próbek."""

    first = _cpu_counters()
    if first is None:
        return 0
    time.sleep(interval)
    second = _cpu_counters()
    if second is None:
        return 0
    total_delta = second[0] - first[0]
    idle_delta = second[1] - first[1]
    if total_delta <= 0:
        return 0
    busy = max(total_delta - idle_delta, 0)
    return min(max(int(round((busy * 100.0) / total_delta)), 0), 100)


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
    executable = which("pidof") or "/bin/pidof"
    if not os.path.exists(executable):
        return None
    try:
        process = subprocess.Popen(
            [executable, name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = _communicate_live(process, 5)
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
    cpu_percent = _cpu_usage()
    load_percent = min(max(int(round(load * 100.0 / cpu_count)), 0), 100)
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
        "cpu_load_percent": load_percent,
        "cpu_count": cpu_count,
        "memory": memory,
        "flash": flash,
        "storage": storage,
        "temperature": _temperature(),
        "enigma2_running": _process_running("enigma2"),
        "opkg_available": bool(which("opkg") or os.path.exists("/usr/bin/opkg")),
    }


def _default_network_route():
    """Zwraca interfejs i bramę domyślnej trasy z /proc/net/route."""

    content = _read_text_file("/proc/net/route")
    for line in content.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 4 or fields[1] != "00000000":
            continue
        try:
            gateway_value = int(fields[2], 16)
            gateway = ".".join(
                str((gateway_value >> shift) & 0xFF)
                for shift in (0, 8, 16, 24)
            )
        except (TypeError, ValueError):
            gateway = "n/d"
        return fields[0], gateway
    return "", ""


def _interface_state(interface):
    if not interface:
        return "n/d"
    return _read_text_file("/sys/class/net/%s/operstate" % interface) or "n/d"


def _interface_ipv4(interface):
    """Odczytuje pierwszy adres IPv4 bez używania powłoki."""

    executable = which("ip")
    if not executable or not interface:
        return "n/d"
    try:
        process = subprocess.Popen(
            [executable, "-4", "-o", "addr", "show", "dev", interface],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        output = _communicate_live(process, 5)
    except (OSError, subprocess.SubprocessError):
        return "n/d"
    for field in output.split():
        if "/" not in field:
            continue
        address = field.split("/", 1)[0]
        try:
            socket.inet_aton(address)
            return field
        except OSError:
            continue
    return "n/d"


def _network_diagnostic_lines(settings=None, progress=None):
    """Wykonuje odczyt trasy, DNS i połączenia TCP do centralnej bazy."""

    lines = []

    def add(message):
        lines.append(message)
        _progress(progress, message)

    add("Diagnostyka sieci Foorys")
    interface, gateway = _default_network_route()
    if interface:
        add(
            "Interfejs: %s (%s), IPv4: %s"
            % (interface, _interface_state(interface), _interface_ipv4(interface))
        )
        add("Brama domyślna: %s" % (gateway or "n/d"))
    else:
        add("Brama domyślna: nie wykryto")

    host = "raw.githubusercontent.com"
    addresses = []
    try:
        infos = socket.getaddrinfo(host, 443, 0, socket.SOCK_STREAM)
        for _family, _socktype, _proto, _canonname, sockaddr in infos:
            address = sockaddr[0]
            if address not in addresses:
                addresses.append(address)
        add("DNS: OK (%s)" % (addresses[0] if addresses else "adres niedostępny"))
    except (OSError, socket.error) as exc:
        add("DNS: BŁĄD (%s)" % _safe_network_error(exc))

    internet_ok = False
    for address in addresses:
        try:
            sock = socket.create_connection((address, 443), timeout=5)
            sock.close()
            internet_ok = True
            break
        except OSError:
            continue
    add("Internet HTTPS: %s" % ("OK" if internet_ok else "BŁĄD"))
    if settings and _setting(settings, "manifest_url", ""):
        add("Centralna baza: adres skonfigurowany")
    else:
        add("Centralna baza: używany adres domyślny")
    return lines, internet_ok


def diagnose_network(_item=None, settings=None, progress=None):
    """Sprawdza interfejs, trasę, DNS i wyjście HTTPS do GitHuba."""

    lines, internet_ok = _network_diagnostic_lines(settings, progress)
    summary = "\n".join(lines)
    return {
        "kind": "network",
        "ok": bool(internet_ok),
        "summary": summary,
    }


def diagnose_internet_speed(_item=None, settings=None, progress=None):
    """Krótki pomiar pobierania bez zapisywania danych na dysku."""

    del _item, settings
    url = "https://speed.cloudflare.com/__down?bytes=3145728"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    response = None
    received = 0
    started = time.time()
    try:
        _progress(progress, "Łączenie z serwerem testowym...")
        response = urlopen(request, timeout=10)
        while received < 3145728:
            chunk = response.read(min(65536, 3145728 - received))
            if not chunk:
                break
            received += len(chunk)
            elapsed = max(time.time() - started, 0.01)
            _progress(progress, "Pobrano %d KB (%.1f Mb/s)" % (received // 1024, (received * 8.0 / elapsed) / 1000000.0))
            if elapsed >= 20:
                break
    except Exception as exc:
        return {
            "kind": "internet-speed",
            "ok": False,
            "summary": "Test prędkości internetu nie powiódł się: %s" % _safe_network_error(exc),
        }
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
    elapsed = max(time.time() - started, 0.01)
    megabits = (received * 8.0 / elapsed) / 1000000.0
    return {
        "kind": "internet-speed",
        "ok": received >= 65536,
        "summary": "Szybki test internetu\n\nPobrano: %.1f MB w %.1f s\nPrędkość pobierania: %.1f Mb/s\n\nWynik orientacyjny — zależy od serwera, Wi-Fi/LAN i chwilowego obciążenia łącza." % (received / 1048576.0, elapsed, megabits),
    }


def _frontend_signal_percent(value):
    """Konwertuje typową wartość SNR/AGC z /proc/stb/frontend na procent."""

    text = to_text(value or "").strip().lower()
    if not text:
        return "n/d"
    try:
        number = int(text, 0)
    except (TypeError, ValueError):
        return text
    if number <= 100:
        return "%d%%" % max(number, 0)
    return "%d%%" % min(max(int(round(number * 100.0 / 65535.0)), 0), 100)


def _frontend_lock(value):
    text = to_text(value or "").strip().lower()
    if not text:
        return None
    if text in ("yes", "true", "locked", "lock"):
        return True
    if text in ("no", "false", "unlocked", "unlock"):
        return False
    if any(token in text for token in ("unlocked", "no lock", "not locked", "idle")):
        return False
    if any(token in text for token in ("locked", "lock", "tuned", "sync")):
        return True
    try:
        return int(text, 0) != 0
    except (TypeError, ValueError):
        return None


def _read_first_text(paths):
    """Zwraca pierwszą dostępną wartość z kilku wariantów procfs."""

    for path in paths:
        value = _read_text_file(path)
        if value:
            return value
    return ""


def _satellite_frontends():
    """Zbiera wykryte frontend-y DVB oraz dostępne wartości sygnału."""

    proc_paths = [
        path for path in glob.glob("/proc/stb/frontend/[0-9]*")
        if os.path.isdir(path)
    ]
    proc_paths.sort()
    device_paths = sorted(glob.glob("/dev/dvb/adapter*/frontend*"))
    count = max(len(proc_paths), len(device_paths))
    result = []
    for index in range(count):
        proc_path = proc_paths[index] if index < len(proc_paths) else ""
        device_path = device_paths[index] if index < len(device_paths) else ""
        values = {}
        for name in ("lock", "tuner_state", "snr", "ber", "agc", "frequency", "system"):
            if proc_path:
                candidates = [os.path.join(proc_path, name)]
                if name == "lock":
                    candidates.extend(
                        [
                            os.path.join(proc_path, "status"),
                            os.path.join(proc_path, "tuner_state"),
                        ]
                    )
                elif name == "snr":
                    candidates.extend(
                        [
                            os.path.join(proc_path, "snr_db"),
                            os.path.join(proc_path, "signal_strength"),
                        ]
                    )
                values[name] = _read_first_text(candidates)
        result.append(
            {
                "index": index + 1,
                "proc_path": proc_path,
                "device": device_path,
                "values": values,
            }
        )
    return result


def diagnose_satellite_connection(_item=None, settings=None, progress=None):
    """Sprawdza obecność frontendów DVB i blokadę sygnału satelitarnego."""

    lines = []

    def add(message):
        lines.append(message)
        _progress(progress, message)

    add("Diagnostyka połączenia satelitarnego Foorys")
    frontends = _satellite_frontends()
    if not frontends:
        add("Tunery DVB: NIE WYKRYTO")
        add("Sprawdź sterownik tunera, przewód antenowy i konfigurację NIM.")
        return {
            "kind": "satellite",
            "ok": False,
            "summary": "\n".join(lines),
            "tuners": 0,
            "locked": 0,
        }

    locked = 0
    for frontend in frontends:
        values = frontend["values"]
        lock = _frontend_lock(values.get("lock"))
        if lock:
            locked += 1
        if lock is True:
            lock_text = "BLOKADA: TAK"
        elif lock is False:
            lock_text = "BLOKADA: NIE"
        else:
            lock_text = "BLOKADA: brak danych"
        device = frontend.get("device") or ("frontend %d" % frontend["index"])
        signal = _frontend_signal_percent(values.get("snr") or values.get("agc"))
        ber = values.get("ber") or "n/d"
        add("Tuner %d (%s): %s, SNR/AGC: %s, BER: %s" % (frontend["index"], device, lock_text, signal, ber))
        if values.get("frequency"):
            add("  częstotliwość: %s" % values["frequency"])

    if locked:
        add("Wynik: sygnał satelitarny z blokadą na %d tunerze(ach)." % locked)
    else:
        add("Wynik: tunery wykryte, ale brak potwierdzonej blokady sygnału.")
        add("Włącz kanał satelitarny i uruchom test ponownie, aby odczytać SNR/BER.")
    return {
        "kind": "satellite",
        "ok": bool(locked),
        "summary": "\n".join(lines),
        "tuners": len(frontends),
        "locked": locked,
    }


def collect_installed_packages(_settings=None):
    """Zwraca pakiety związane z E2iPlayerem i softcamami (tylko odczyt)."""

    executable = which("opkg") or "/usr/bin/opkg"
    if not os.path.exists(executable):
        return {"available": False, "packages": []}
    try:
        process = subprocess.Popen(
            [executable, "list-installed"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        output = _communicate_live(process, 30)
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
            ensure_dir(path)
        except OSError as exc:
            raise OperationError("Nie można utworzyć %s: %s" % (label, exc))
    return path


def _storage_directory(settings):
    """Wybiera magazyn danych, omijając niezamontowany /media/hdd."""

    requested = os.path.abspath(
        _setting(settings, "storage_dir", "/media/hdd/e2foorys")
    )
    usage = _filesystem_usage(requested)
    if usage.get("mounted", True) and usage.get("free", 0) >= MIN_STORAGE_FREE:
        return _ensure_absolute_directory(requested, "katalog danych")

    fallback = os.path.abspath(
        _setting(settings, "storage_fallback_dir", STORAGE_FALLBACK_DIR)
    )
    fallback_usage = _filesystem_usage(fallback)
    if fallback_usage.get("free", 0) < MIN_STORAGE_FREE:
        raise OperationError(
            "Brak miejsca w katalogu danych (%s) i w awaryjnym rootfs (%s)."
            % (requested, fallback)
        )
    return _ensure_absolute_directory(fallback, "awaryjny katalog danych")


def _validate_download_url(url):
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https", "file"):
        raise OperationError("Do pobierania dozwolone są wyłącznie URL-e HTTP(S) lub file://.")


def _read_response(response, limit):
    chunks = []
    total = 0
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            raise OperationError("Pobrany plik przekracza limit %d MB." % (limit // (1024 * 1024)))
    return b"".join(chunks)


def _safe_network_error(exc):
    """Zwraca komunikat błędu bez wypisywania prywatnego URL-a M3U."""

    code = getattr(exc, "code", None)
    if code:
        return "serwer zwrócił HTTP %s" % code
    reason = getattr(exc, "reason", None)
    if reason:
        return "brak połączenia (%s)" % reason
    return "brak połączenia lub odrzucona odpowiedź"


def _download_iptv_text(url, progress=None):
    """Pobiera playlistę M3U bez logowania URL-a zawierającego dane konta."""

    _validate_download_url(url)
    _progress(progress, "Pobieram playlistę Foorys IPTV...")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
    response = None
    try:
        response = urlopen(request, timeout=60)
        raw = _read_response(response, 32 * 1024 * 1024)
    except Exception as exc:
        raise OperationError("Nie udało się pobrać playlisty Foorys IPTV: %s" % _safe_network_error(exc))
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    if not raw:
        raise OperationError("Serwer zwrócił pustą playlistę Foorys IPTV.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", "replace")
    if "#EXTINF" not in text.upper():
        raise OperationError("Pobrany plik nie jest poprawną playlistą M3U.")
    _progress(progress, "Playlista M3U pobrana — analizuję kanały...")
    return text


def _clean_iptv_text(value, fallback=""):
    value = to_text(value or "").replace("\r", " ").replace("\n", " ").strip()
    value = re.sub(r"\s+", " ", value)
    return value[:240] or fallback


def _clean_iptv_name(value, fallback=""):
    """Usuwa techniczny prefiks kraju z nazwy wyświetlanej w bukiecie."""

    value = _clean_iptv_text(value, fallback)
    value = re.sub(r"^PL\s*(?::|\|)\s*", "", value, flags=re.IGNORECASE)
    return value.strip() or fallback


def _clean_iptv_url(value):
    """Czyści atrybut URL bez skracania linków z parametrami playlisty."""

    value = to_text(value or "").replace("\r", "").replace("\n", "").strip()
    return value[:4096]


def parse_iptv_m3u(text):
    """Zwraca kanały live z playlisty M3U/M3U+ w kolejności źródłowej."""

    if not isinstance(text, string_types):
        raise OperationError("Playlista IPTV ma nieprawidłowy format tekstowy.")
    if isinstance(text, binary_type):
        try:
            text = text.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = text.decode("latin-1", "replace")
    entries = []
    current = None
    pending_group = ""
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("#EXTINF:"):
            payload = line.split(",", 1)
            header = payload[0]
            title = payload[1] if len(payload) > 1 else ""
            attributes = {}
            for match in _IPTV_ATTRIBUTE_RE.finditer(header):
                value = match.group(2) or match.group(3) or match.group(4) or ""
                key = match.group(1).lower()
                attributes[key] = _clean_iptv_url(value) if key == "tvg-logo" else _clean_iptv_text(value)
            name = _clean_iptv_name(
                attributes.get("tvg-name") or title,
                "Kanał %d" % (len(entries) + 1),
            )
            current = {
                "name": name,
                "tvg_id": _clean_iptv_text(attributes.get("tvg-id")),
                "tvg_logo": _clean_iptv_url(attributes.get("tvg-logo")),
                "group": _clean_iptv_text(attributes.get("group-title") or pending_group),
            }
            continue
        if upper.startswith("#EXTGRP:"):
            pending_group = _clean_iptv_text(line.split(":", 1)[1] if ":" in line else "")
            if current is not None and not current.get("group"):
                current["group"] = pending_group
            continue
        if line.startswith("#"):
            continue
        if current is None:
            continue
        stream_url = line.strip()
        scheme = urlparse(stream_url).scheme.lower()
        if scheme not in ("http", "https", "rtmp", "rtsp", "udp"):
            current = None
            continue
        if "\r" in stream_url or "\n" in stream_url:
            current = None
            continue
        current["url"] = stream_url
        entries.append(current)
        current = None
        if len(entries) >= IPTV_MAX_CHANNELS:
            break
    if not entries:
        raise OperationError("Playlista nie zawiera kanałów live z obsługiwanym adresem strumienia.")
    return entries


def _iptv_service_reference(entry, index):
    """Buduje stabilny service reference i nazwę piconu dla kanału IPTV."""

    seed = "%s|%s|%s" % (entry.get("url", ""), entry.get("tvg_id", ""), index)
    digest = hashlib.sha1(seed.encode("utf-8", "replace")).hexdigest()
    service_id = int(digest[:10], 16) % 0x7FFFFFFF
    if service_id == 0:
        service_id = index + 1
    bouquet_id1 = service_id // 65535
    bouquet_id2 = service_id % 65535
    unique_ref = int(hashlib.sha1(b"e2foorys-iptv").hexdigest()[:8], 16) % 0x7FFFFFFF
    encoded_url = quote(
        entry["url"],
        safe="/?=&%@+;,.-_~[]",
    )
    service_ref = "4097:0:1:%x:%x:%x:0:0:0:0:%s" % (
        bouquet_id1,
        bouquet_id2,
        unique_ref,
        encoded_url,
    )
    picon_name = "%s.png" % "_".join(service_ref.split(":")[:10])
    return service_ref, picon_name


def _write_text_atomic(path, content):
    parent = os.path.dirname(os.path.abspath(path))
    ensure_dir(parent)
    temporary = path + ".part"
    try:
        with open_text(temporary, "w", newline="\n") as handle:
            handle.write(to_text(content))
        replace_file(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _bouquets_tv_with_bouquet(path, bouquet_filename):
    """Dodaje wskazany bukiet do bouquets.tv, usuwając jego duplikaty."""

    registration = (
        '#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "%s" ORDER BY bouquet'
        % bouquet_filename
    )
    try:
        with open_text(path, "r", errors="replace") as handle:
            lines = handle.read().splitlines()
    except (OSError, IOError):
        lines = []
    if not lines:
        lines = ["#NAME TV"]
    marker = 'FROM BOUQUET "%s"' % bouquet_filename
    lines = [line for line in lines if marker not in line]
    lines.append(registration)
    return "\n".join(lines).rstrip() + "\n"


def _download_iptv_picon(url, progress=None):
    """Pobiera pojedynczy PNG piconu bez ujawniania URL-a z playlisty."""

    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https", "file"):
        raise OperationError("picon ma nieobsługiwany adres")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    response = None
    try:
        response = urlopen(request, timeout=25)
        data = _read_response(response, IPTV_MAX_PICON_BYTES)
    except Exception as exc:
        raise OperationError(_safe_network_error(exc))
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise OperationError("odpowiedź nie jest plikiem PNG")
    return data


def fetch_manifest(manifest_url):
    """Pobiera i waliduje manifest, rozwijając względne URL-e."""

    _validate_download_url(manifest_url)
    # Raw GitHub może przez chwilę zwracać wcześniejszą wersję pliku. Znacznik
    # czasu i nagłówki wymuszają pobranie świeżego katalogu po ZIELONYM.
    separator = "&" if "?" in manifest_url else "?"
    download_url = "%s%se2foorys_refresh=%d" % (manifest_url, separator, int(time.time() * 1000))
    request = Request(download_url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache", "Pragma": "no-cache"})
    response = None
    try:
        response = urlopen(request, timeout=25)
        raw = _read_response(response, MANIFEST_LIMIT)
    except Exception as exc:
        raise OperationError("Nie można pobrać manifestu: %s" % exc)
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    manifest = parse_manifest(raw)
    for collection_name in ("channel_lists", "plugins", "picons"):
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
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", to_text(value or ""))
    value = value.strip("._")
    return value or fallback


def _format_size(value):
    units = ("B", "KB", "MB", "GB", "TB")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/d"
    index = 0
    while abs(number) >= 1024 and index < len(units) - 1:
        number /= 1024.0
        index += 1
    return "%d %s" % (int(number), units[index]) if index == 0 else "%.1f %s" % (number, units[index])


def download_verified(url, destination, expected_sha256, max_bytes=DOWNLOAD_LIMIT, progress=None):
    """Pobiera plik do .part, sprawdza SHA-256 i atomowo zmienia nazwę."""

    _validate_download_url(url)
    _progress(progress, "Pobieranie: %s" % url)
    expected_sha256 = to_text(expected_sha256).lower()
    parent = os.path.dirname(os.path.abspath(destination))
    ensure_dir(parent)
    temporary = destination + ".part"
    if os.path.exists(temporary):
        os.unlink(temporary)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    received = 0
    last_report = 0
    response = None
    try:
        response = urlopen(request, timeout=60)
        with open(temporary, "wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > max_bytes:
                    raise OperationError("Pobrany plik przekracza dozwolony limit.")
                output.write(chunk)
                if received - last_report >= 5 * 1024 * 1024:
                    _progress(progress, "Pobrano %s" % _format_size(received))
                    last_report = received
        _progress(progress, "Pobrano %s — sprawdzam SHA-256..." % _format_size(received))
        if not verify_sha256(temporary, expected_sha256):
            actual = sha256_file(temporary)
            raise OperationError(
                "Nieprawidłowa suma SHA-256. Oczekiwano %s, otrzymano %s."
                % (expected_sha256, actual)
            )
        replace_file(temporary, destination)
        _progress(progress, "SHA-256 OK — plik gotowy do instalacji.")
    except OperationError:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    except Exception as exc:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise OperationError("Pobieranie nie powiodło się: %s" % exc)
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
    return destination


def _communicate_live(process, timeout, progress=None):
    """Czyta stdout procesu liniami i przekazuje je do konsoli GUI."""

    output = []
    deadline = time.time() + timeout
    stream = process.stdout
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            process.kill()
            process.communicate()
            raise OperationError("Proces przekroczył limit czasu.")
        if process.poll() is not None:
            break
        try:
            ready, _unused_write, _unused_error = select.select(
                [stream], [], [], min(0.25, remaining)
            )
        except (OSError, ValueError):
            ready = [stream]
        if not ready:
            continue
        line = stream.readline()
        if not line:
            if process.poll() is not None:
                break
            continue
        # Python 3 returns bytes unless universal_newlines=True was supplied.
        # Every caller receives text; Python 2.7 remains supported via to_text.
        line = to_text(line)
        output.append(line)
        _progress(progress, line.rstrip())

    trailing = stream.read()
    if trailing:
        trailing = to_text(trailing)
        output.append(trailing)
        for line in trailing.splitlines():
            _progress(progress, line.rstrip())
    process.wait()
    return "".join(output)


def _timestamp():
    return time.strftime("%Y%m%d-%H%M%S")


def _backup_existing(source, backup_root, metadata):
    if not os.path.isfile(source):
        return None
    ensure_dir(backup_root)
    target = os.path.join(backup_root, os.path.basename(source))
    shutil.copy2(source, target)
    metadata.append({"source": source, "backup": target, "name": os.path.basename(source)})
    return target


def _write_json(path, data):
    ensure_dir(os.path.dirname(os.path.abspath(path)))
    temporary = path + ".part"
    with open_text(temporary, "w") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    replace_file(temporary, path)


def install_channel_list(item, settings, progress=None):
    """Pobiera archiwum listy kanałów i instaluje tylko znane pliki E2."""

    _progress(progress, "Przygotowuję katalog danych i kopię bezpieczeństwa...")
    storage = _storage_directory(settings)
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
    download_verified(item["url"], archive_path, item["sha256"], progress=progress)

    staging = tempfile.mkdtemp(prefix="e2foorys-channels-", dir=storage)
    backup_metadata = []
    installed = []
    try:
        try:
            _progress(progress, "Rozpakowuję archiwum listy kanałów...")
            extract_archive(archive_path, staging)
        except ArchiveError as exc:
            raise OperationError("Archiwum listy kanałów jest nieprawidłowe: %s" % exc)
        source_files = find_channel_files(staging)
        if not source_files:
            raise OperationError("Archiwum nie zawiera rozpoznanych plików listy kanałów.")

        backup_root = os.path.join(storage, "backups", "channels-%s" % _timestamp())
        create_backup = bool(_setting(settings, "create_backup", True))
        seen_names = set()
        _progress(progress, "Zapisuję rozpoznane pliki do %s..." % destination)
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
        _progress(progress, "Lista kanałów: operacja plikowa zakończona.")
        shutil.rmtree(staging, ignore_errors=True)


def _iptv_credentials_playlist_url(settings, username_key, password_key, error_message):
    """Buduje link M3U z lokalnych danych dostępowych."""

    dns = _setting(settings, "iptv_dns", IPTV_FORYS_DNS)
    username = _setting(settings, username_key, "")
    password = _setting(settings, password_key, "")
    if not username or not password:
        raise OperationError(error_message)
    if "://" not in dns:
        dns = "http://%s:%d" % (dns.rstrip("/"), IPTV_FORYS_PORT)
    parsed = urlparse(dns)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise OperationError("DNS Foorys IPTV ma nieprawidłowy format.")
    base = dns.rstrip("/")
    query = urlencode(
        {
            "username": username,
            "password": password,
            "type": "m3u_plus",
            "output": "ts",
        }
    )
    return "%s/get.php?%s" % (base, query)


def _iptv_playlist_url(settings):
    """Zwraca prywatny link M3U z ustawień, bez zapisywania go w repozytorium."""

    direct_url = _setting(settings, "iptv_m3u_url", "")
    if direct_url:
        _validate_download_url(direct_url)
        return direct_url
    return _iptv_credentials_playlist_url(
        settings,
        "iptv_username",
        "iptv_password",
        "W Foorys IPTV → Ustawienia IPTV wpisz link M3U albo DNS, login i hasło.",
    )


def _install_iptv_picons(entries, target, progress=None):
    """Pobiera picony PNG z atrybutu tvg-logo dla zapisanych usług."""

    target = _ensure_absolute_directory(target, "katalog piconów IPTV")
    logo_entries = [entry for entry in entries if entry.get("tvg_logo")]
    if not logo_entries:
        return {"installed": 0, "failed": 0, "available": 0}

    temporary_root = tempfile.mkdtemp(prefix="e2foorys-iptv-picons-")
    logo_cache = {}
    installed = 0
    failed = 0
    attempted = 0
    try:
        total = min(len(logo_entries), IPTV_MAX_PICONS)
        for index, entry in enumerate(entries):
            logo_url = entry.get("tvg_logo", "")
            if not logo_url:
                continue
            if attempted >= IPTV_MAX_PICONS:
                break
            attempted += 1
            if logo_url not in logo_cache:
                _progress(progress, "Pobieram picon IPTV %d/%d..." % (attempted, total))
                try:
                    data = _download_iptv_picon(logo_url, progress=progress)
                    source = os.path.join(temporary_root, "logo-%d.png" % attempted)
                    with open(source, "wb") as handle:
                        handle.write(data)
                    logo_cache[logo_url] = source
                except Exception:
                    logo_cache[logo_url] = None
                    failed += 1
                    continue
            source = logo_cache.get(logo_url)
            if not source or not os.path.isfile(source):
                continue
            try:
                atomic_copy(source, os.path.join(target, entry["picon_name"]))
                installed += 1
            except Exception:
                failed += 1
        _progress(progress, "Picony IPTV: zapisano %d, pominięto %d." % (installed, failed))
        return {"installed": installed, "failed": failed, "available": attempted}
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def _install_iptv_bouquet(entries, settings, bouquet_name, bouquet_filename,
                          progress=None):
    """Zapisuje playlistę jako bukiet bez automatycznego pobierania piconów."""

    destination = _ensure_absolute_directory(
        _setting(settings, "enigma2_dir", "/etc/enigma2"),
        "katalog Enigma2",
    )
    storage = _storage_directory(settings)
    if len(entries) >= IPTV_MAX_CHANNELS:
        _progress(progress, "Playlista jest większa — używam pierwszych %d kanałów." % IPTV_MAX_CHANNELS)

    bouquet_lines = ["#NAME %s" % bouquet_name]
    for index, entry in enumerate(entries, 1):
        service_ref, picon_name = _iptv_service_reference(entry, index)
        entry["picon_name"] = picon_name
        bouquet_lines.append("#SERVICE %s" % service_ref)
        bouquet_lines.append("#DESCRIPTION %s" % entry["name"])
    bouquet_content = "\n".join(bouquet_lines) + "\n"

    bouquet_path = os.path.join(destination, bouquet_filename)
    bouquets_path = os.path.join(destination, "bouquets.tv")
    backup_metadata = []
    backup_root = os.path.join(
        storage,
        "backups",
        "iptv-%s" % _timestamp(),
    )
    if bool(_setting(settings, "create_backup", True)):
        _backup_existing(bouquet_path, backup_root, backup_metadata)
        _backup_existing(bouquets_path, backup_root, backup_metadata)

    _progress(progress, "Zapisuję %d kanałów do bukietu %s..." % (len(entries), bouquet_name))
    _write_text_atomic(bouquet_path, bouquet_content)
    _write_text_atomic(
        bouquets_path,
        _bouquets_tv_with_bouquet(bouquets_path, bouquet_filename),
    )

    picon_result = {"installed": 0, "failed": 0, "available": 0}
    _progress(progress, "Picony IPTV nie są pobierane automatycznie.")

    if backup_metadata:
        _write_json(
            os.path.join(backup_root, "backup.json"),
            {"type": "iptv", "created_at": _timestamp(), "files": backup_metadata},
        )
    _progress(progress, "%s: bukiet jest gotowy." % bouquet_name)
    return {
        "kind": "iptv",
        "name": bouquet_name,
        "bouquet": bouquet_path,
        "bouquets_file": bouquets_path,
        "channels": len(entries),
        "picons": picon_result.get("installed", 0),
        "picon_failures": picon_result.get("failed", 0),
        "backup": backup_root if backup_metadata else None,
    }


def install_iptv_playlist(_item, settings, progress=None):
    """Tworzy osobny bukiet Foorys IPTV bez pobierania piconów."""

    _progress(progress, "Przygotowuję bukiet Foorys IPTV...")
    playlist = _download_iptv_text(_iptv_playlist_url(settings), progress=progress)
    entries = parse_iptv_m3u(playlist)
    return _install_iptv_bouquet(
        entries,
        settings,
        IPTV_BOUQUET_NAME,
        IPTV_BOUQUET_FILENAME,
        progress=progress,
    )


def install_iptv_picons(_item, settings, progress=None):
    """Pobiera picony IPTV osobno, na wyraźne żądanie użytkownika."""

    _progress(progress, "Przygotowuję osobne pobieranie piconów IPTV...")
    playlist = _download_iptv_text(_iptv_playlist_url(settings), progress=progress)
    entries = parse_iptv_m3u(playlist)
    for index, entry in enumerate(entries, 1):
        _service_ref, picon_name = _iptv_service_reference(entry, index)
        entry["picon_name"] = picon_name
    result = _install_iptv_picons(
        entries,
        _setting(settings, "picon_dir", "/usr/share/enigma2/picon"),
        progress=progress,
    )
    _progress(progress, "Picony IPTV: zakończono osobną aktualizację.")
    return {
        "kind": "iptv_picons",
        "name": "Picony Foorys IPTV",
        "channels": len(entries),
        "picons": result.get("installed", 0),
        "picon_failures": result.get("failed", 0),
    }


def install_oscam_dvbapi(item, settings, progress=None):
    """Pobiera oscam.dvbapi i podmienia go atomowo po wykonaniu kopii."""

    _progress(progress, "Przygotowuję aktualizację oscam.dvbapi...")
    storage = _storage_directory(settings)
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
    download_verified(item["url"], downloaded, item["sha256"], max_bytes=16 * 1024 * 1024, progress=progress)

    backup_metadata = []
    backup_root = os.path.join(storage, "backups", "oscam-%s" % _timestamp())
    if bool(_setting(settings, "create_backup", True)):
        _backup_existing(target, backup_root, backup_metadata)
    _progress(progress, "Zapisuję plik do %s..." % target)
    atomic_copy(downloaded, target)
    if backup_metadata:
        _write_json(
            os.path.join(backup_root, "backup.json"),
            {"type": "oscam.dvbapi", "created_at": _timestamp(), "files": backup_metadata},
        )
    _progress(progress, "oscam.dvbapi: zapis zakończony.")
    return {
        "kind": "oscam.dvbapi",
        "target": target,
        "version": item.get("version", ""),
        "backup": backup_root if backup_metadata else None,
    }


def install_current_oscam_dvbapi(_item, settings, progress=None):
    """Zapisuje aktualny profil Foorys z dokładnie trzema regułami P:."""

    _progress(progress, "Tworzę aktualny oscam.dvbapi z trzema regułami Foorys...")
    storage = _storage_directory(settings)
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
        with open_text(temporary, "w") as handle:
            handle.write("\n".join(FOORYS_OSCAM_DVBAPI_LINES) + "\n")
        _progress(progress, "Zapisuję dokładnie: P:1884, P:0B01, P:1861...")
        atomic_copy(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

    if backup_metadata:
        _write_json(
            os.path.join(backup_root, "backup.json"),
            {"type": "oscam.dvbapi", "created_at": _timestamp(), "files": backup_metadata},
        )
    _progress(progress, "oscam.dvbapi: zapis zakończony pomyślnie.")
    return {
        "kind": "oscam.dvbapi",
        "target": target,
        "version": "foorys-current",
        "lines": list(FOORYS_OSCAM_DVBAPI_LINES),
        "backup": backup_root if backup_metadata else None,
    }


def _find_7zip():
    for name in ("7za", "7z", "7zz"):
        executable = which(name)
        if executable:
            return executable
    for executable in ("/usr/bin/7za", "/usr/bin/7z", "/usr/bin/7zz"):
        if os.path.isfile(executable) and os.access(executable, os.X_OK):
            return executable
    return None


def _extract_picons(archive_path, destination, progress=None):
    """Rozpakowuje ZIP/tar lub 7z do katalogu tymczasowego."""

    lower_name = archive_path.lower()
    if not lower_name.endswith((".7z", ".7zip")):
        try:
            _progress(progress, "Rozpakowuję archiwum piconów...")
            extract_archive(archive_path, destination)
        except ArchiveError as exc:
            raise OperationError("Archiwum piconów jest nieprawidłowe: %s" % exc)
        return

    executable = _find_7zip()
    if not executable:
        raise OperationError(
            "Brak 7za/7z na dekoderze. Najpierw zainstaluj Chocholousek Picons "
            "albo pakiet p7zip z feedu obrazu."
        )
    try:
        _progress(progress, "Rozpakowuję 7z przy pomocy %s..." % executable)
        process = subprocess.Popen(
            [executable, "x", "-y", "-o%s" % destination, archive_path, "*.png"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        output = _communicate_live(process, 900, progress=progress)
    except OSError as exc:
        raise OperationError("Nie można uruchomić 7za: %s" % exc)
    if process.returncode != 0:
        raise OperationError(
            "7za zakończył się kodem %s:\n%s"
            % (process.returncode, (output or "")[-3000:])
        )


def install_picons(item, settings, progress=None):
    """Pobiera zweryfikowany pakiet piconów i aktualizuje pliki PNG."""

    _progress(progress, "Przygotowuję aktualizację piconów...")
    target = _ensure_absolute_directory(
        _setting(settings, "picon_dir", "/usr/share/enigma2/picon"),
        "katalog piconów",
    )
    temporary_root = tempfile.mkdtemp(prefix="e2foorys-picons-")
    archive_extension = os.path.splitext(urlparse(item["url"]).path)[1].lower() or ".archive"
    archive_path = os.path.join(
        temporary_root,
        "picons-%s-%s%s"
        % (
            _safe_filename(item.get("id")),
            _safe_filename(item.get("version")),
            archive_extension,
        ),
    )
    staging = os.path.join(temporary_root, "staging")
    try:
        download_verified(item["url"], archive_path, item["sha256"], progress=progress)
        ensure_dir(staging)
        _extract_picons(archive_path, staging, progress=progress)
        source_files = find_picon_files(staging)
        if not source_files:
            raise OperationError("Archiwum nie zawiera plików PNG piconów.")

        staging_root = os.path.realpath(staging)
        names = set()
        total_size = 0
        for source in source_files:
            if os.path.islink(source) or not os.path.isfile(source):
                raise OperationError("Archiwum piconów zawiera niedozwolony plik.")
            if not is_path_within(staging_root, source):
                raise OperationError("Picon wychodzi poza katalog tymczasowy.")
            filename = os.path.basename(source)
            key = filename.lower()
            if key in names:
                raise OperationError("Archiwum zawiera duplikat piconu: %s" % filename)
            names.add(key)
            total_size += os.path.getsize(source)

        try:
            stats = os.statvfs(target)
            free = int(stats.f_bavail) * int(stats.f_frsize or stats.f_bsize or 4096)
            if free < total_size:
                raise OperationError(
                    "Za mało miejsca w katalogu piconów: potrzeba %s, wolne %s."
                    % (_format_size(total_size), _format_size(free))
                )
        except AttributeError:
            pass

        installed = []
        _progress(progress, "Aktualizuję %d piconów w %s..." % (len(source_files), target))
        for source in source_files:
            filename = os.path.basename(source)
            atomic_copy(source, os.path.join(target, filename))
            installed.append(filename)
        _progress(progress, "Picony: aktualizacja zakończona pomyślnie.")
        return {
            "kind": "picons",
            "name": item.get("name", item.get("id", "picony")),
            "version": item.get("version", ""),
            "target": target,
            "installed_count": len(installed),
            "installed": installed,
            "mode": "incremental",
        }
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def list_backups(settings=None):
    """Zwraca krótką listę kopii zapisanych przez plugin."""

    root = os.path.join(_storage_directory(settings or {}), "backups")
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
                with open_text(backup_json, "r", errors="replace") as handle:
                    backup_type = json.load(handle).get("type", backup_type)
            except (OSError, IOError, TypeError, ValueError):
                pass
        result.append({"name": name, "path": path, "type": metadata.get("type", backup_type)})
    return {"root": root, "backups": result}


def _run_opkg(package_path, timeout=600, progress=None):
    executable = which("opkg") or "/usr/bin/opkg"
    if not os.path.exists(executable):
        raise OperationError("Nie znaleziono programu opkg na dekoderze.")
    _progress(progress, "Uruchamiam opkg install %s..." % package_path)
    try:
        process = subprocess.Popen(
            [executable, "install", package_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        output = _communicate_live(process, timeout, progress=progress)
    except OSError as exc:
        raise OperationError("Nie można uruchomić opkg: %s" % exc)
    if process.returncode != 0:
        raise OperationError(
            "opkg zakończył się kodem %s:\n%s" % (process.returncode, output[-3000:])
        )
    return output[-3000:]


def _run_shell_command(command, timeout=900, progress=None):
    """Uruchamia wyłącznie stałą akcję pluginu przez powłokę dekodera."""

    if not isinstance(command, string_types) or not command.strip():
        raise OperationError("Pusta komenda instalacyjna.")
    if not os.path.exists("/bin/sh"):
        raise OperationError("Na dekoderze brakuje /bin/sh.")
    _progress(progress, "Uruchamiam polecenie instalacyjne...")
    try:
        process = subprocess.Popen(
            ["/bin/sh", "-c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        output = _communicate_live(process, timeout, progress=progress)
    except OSError as exc:
        raise OperationError("Nie można uruchomić instalatora: %s" % exc)
    if process.returncode != 0:
        raise OperationError(
            "Instalator zakończył się kodem %s:\n%s"
            % (process.returncode, output[-3000:])
        )
    return output[-3000:]


def install_e2iplayer(_item, _settings, progress=None):
    """Instaluje bieżącą gałąź Python 3 E2iPlayer z OE-Mirrors."""

    if sys.version_info[0] < 3:
        raise OperationError(
            "Ten instalator E2iPlayer wymaga obrazu Enigma2 z Pythonem 3. "
            "Pozostałe funkcje E2-Foorys nadal działają na Pythonie 2.7."
        )
    output = _run_shell_command(E2IPLAYER_INSTALL_COMMAND, progress=progress)
    return {"kind": "e2iplayer", "name": "E2iPlayer", "output": output}


def patch_e2iplayer(_item, _settings, progress=None):
    """Nakłada patch hosttorrentyts na zainstalowany E2iPlayer."""

    if sys.version_info[0] < 3:
        raise OperationError("Patch E2iPlayer jest przeznaczony dla wersji Python 3.")
    output = _run_shell_command(E2IPLAYER_PATCH_COMMAND, progress=progress)
    return {"kind": "e2iplayer-patch", "name": "E2iPlayer patch", "output": output}


def install_oscam_stable(_item, _settings, progress=None):
    """Instaluje oscam-stable z feedu OEA zgodnie z komendą użytkownika."""

    output = _run_shell_command(OSCAM_STABLE_COMMAND, progress=progress)
    return {
        "kind": "oscam-stable",
        "name": "Oscam stable",
        "package": "enigma2-plugin-softcams-oscam-stable",
        "output": output,
    }


def install_public_softcam(item, _settings, progress=None):
    """Instaluje tylko publiczne pakiety softcam jawnie dopuszczone przez plugin."""

    softcam_id = to_text((item or {}).get("id", ""))
    package_info = PUBLIC_SOFTCAM_PACKAGES.get(softcam_id)
    if not package_info:
        raise OperationError("Nieobsługiwany pakiet softcam.")
    package_name = package_info["package"]
    output = _run_shell_command("opkg update && opkg install %s" % package_name, progress=progress)
    return {
        "kind": "softcam",
        "name": package_info["name"],
        "package": package_name,
        "output": output,
    }


def validate_root_password(password):
    """Waliduje hasło przekazywane jednorazowo do chpasswd."""

    if not isinstance(password, string_types):
        raise OperationError("Nieprawidłowe hasło.")
    if len(password) < 8:
        raise OperationError("Hasło roota musi mieć co najmniej 8 znaków.")
    if len(password) > 128:
        raise OperationError("Hasło roota może mieć maksymalnie 128 znaków.")
    if ":" in password or "\n" in password or "\r" in password:
        raise OperationError("Hasło nie może zawierać dwukropka ani znaku nowej linii.")
    if any(ord(character) < 32 for character in password):
        raise OperationError("Hasło nie może zawierać znaków kontrolnych.")


def change_root_password(password, progress=None):
    """Zmienia hasło konta root bez zapisywania go w konfiguracji lub logu."""

    validate_root_password(password)
    executable = which("chpasswd") or "/usr/sbin/chpasswd"
    if not os.path.exists(executable):
        raise OperationError("Nie znaleziono narzędzia chpasswd na dekoderze.")
    _progress(progress, "Zmiana hasła root...")
    try:
        process = subprocess.Popen(
            [executable],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        payload = ("root:%s\n" % to_text(password)).encode("utf-8")
        output, _unused = process.communicate(payload)
        output = to_text(output)
    except OSError as exc:
        raise OperationError("Nie można uruchomić chpasswd: %s" % exc)
    if process.returncode != 0:
        raise OperationError("Zmiana hasła nie powiodła się:\n%s" % (output or "brak szczegółów"))
    _progress(progress, "Hasło root zostało zmienione.")
    return {"kind": "root-password", "name": "Hasło root", "output": "Hasło zostało zmienione."}


def install_plugin_package(item, settings, progress=None):
    """Pobiera i instaluje pakiet .ipk przez opkg."""

    required_python = int(item.get("min_python_major", 0) or 0)
    if required_python and sys.version_info[0] < required_python:
        raise OperationError(
            "Pakiet '%s' wymaga Pythona %d lub nowszego. Ten obraz używa Pythona %d."
            % (item.get("name", item.get("id", "plugin")), required_python, sys.version_info[0])
        )
    package_type = to_text(item.get("package_type", "ipk")).lower()
    if package_type not in ("ipk", "deb"):
        raise OperationError("Nieobsługiwany typ pakietu: %s" % package_type)
    storage = _storage_directory(settings)
    packages = _ensure_absolute_directory(os.path.join(storage, "packages"), "pakiety")
    extension = "." + package_type
    filename = "%s-%s%s" % (
        _safe_filename(item.get("id")),
        _safe_filename(item.get("version")),
        extension,
    )
    package_path = os.path.join(packages, filename)
    download_verified(item["url"], package_path, item["sha256"], progress=progress)
    output = _run_opkg(package_path, progress=progress)
    return {
        "kind": "plugin",
        "name": item.get("name", item.get("id", "")),
        "version": item.get("version", ""),
        "package": package_path,
        "output": output,
    }
