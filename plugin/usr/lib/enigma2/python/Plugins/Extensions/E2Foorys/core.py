# -*- coding: utf-8 -*-

"""Czyste, niezależne od Enigma2 funkcje bezpieczeństwa i walidacji.

Ten moduł nie importuje żadnych klas z Enigma2. Dzięki temu można go testować
na komputerze, a część odpowiedzialna za pobieranie i instalację pozostaje
łatwa do rozbudowy.
"""

from __future__ import absolute_import

import hashlib
import json
import os
import posixpath
import re
import shutil
import stat
import tarfile
import tempfile
import zipfile


class ManifestError(ValueError):
    """Manifest ma nieprawidłowy format albo zawiera niedozwolone dane."""


class ArchiveError(ValueError):
    """Archiwum nie może zostać bezpiecznie rozpakowane."""


SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
ALLOWED_URL_SCHEMES = ("http", "https", "file")

# Pliki, które mogą być zapisane przez moduł list kanałów.
CHANNEL_FILE_NAMES = frozenset(
    (
        "lamedb",
        "lamedb5",
        "bouquets.tv",
        "bouquets.radio",
        "satellites.xml",
        "blacklist",
        "whitelist",
    )
)


def version_is_newer(remote, current):
    """Porównuje wersje numerycznie, tolerując prefiksy typu v1.2.3."""

    def key(value):
        numbers = re.findall(r"\d+", str(value or ""))
        return tuple(int(number) for number in numbers) or (0,)

    remote_key = key(remote)
    current_key = key(current)
    length = max(len(remote_key), len(current_key))
    return remote_key + (0,) * (length - len(remote_key)) > current_key + (0,) * (length - len(current_key))


def _text(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ManifestError("Pole '%s' musi być niepustym tekstem." % field_name)
    return value.strip()


def validate_sha256(value, field_name="sha256"):
    value = _text(value, field_name)
    if not SHA256_RE.match(value):
        raise ManifestError("Pole '%s' musi zawierać 64 znaki SHA-256." % field_name)
    return value.lower()


def _validate_url(value, field_name="url"):
    value = _text(value, field_name)
    # Manifest może używać URL-i względnych. Zostaną rozwinięte przez
    # operations.fetch_manifest() względem adresu manifestu.
    if "://" in value:
        scheme = value.split("://", 1)[0].lower()
        if scheme not in ALLOWED_URL_SCHEMES:
            raise ManifestError(
                "Niedozwolony schemat URL w polu '%s': %s" % (field_name, scheme)
            )
    return value


def _validate_download_item(item, collection_name, index):
    if not isinstance(item, dict):
        raise ManifestError("Element %s[%d] musi być obiektem JSON." % (collection_name, index))
    item_id = _text(item.get("id"), "%s[%d].id" % (collection_name, index))
    name = _text(item.get("name"), "%s[%d].name" % (collection_name, index))
    url = _validate_url(item.get("url"), "%s[%d].url" % (collection_name, index))
    checksum = validate_sha256(
        item.get("sha256"), "%s[%d].sha256" % (collection_name, index)
    )
    version = str(item.get("version", "")).strip()
    if not version:
        raise ManifestError("%s[%d].version nie może być puste." % (collection_name, index))
    result = dict(item)
    result.update({"id": item_id, "name": name, "url": url, "sha256": checksum, "version": version})
    return result


def normalize_manifest(data):
    """Waliduje manifest i zwraca jego kopię w ujednoliconym formacie."""

    if not isinstance(data, dict):
        raise ManifestError("Manifest musi być obiektem JSON.")

    schema_version = data.get("schema_version", 1)
    if schema_version != 1:
        raise ManifestError("Nieobsługiwana wersja manifestu: %s" % schema_version)

    channel_lists = data.get("channel_lists", [])
    plugins = data.get("plugins", [])
    picons = data.get("picons", [])
    if not isinstance(channel_lists, list):
        raise ManifestError("Pole 'channel_lists' musi być tablicą.")
    if not isinstance(plugins, list):
        raise ManifestError("Pole 'plugins' musi być tablicą.")
    if not isinstance(picons, list):
        raise ManifestError("Pole 'picons' musi być tablicą.")

    result = dict(data)
    result["schema_version"] = 1
    result["channel_lists"] = [
        _validate_download_item(item, "channel_lists", index)
        for index, item in enumerate(channel_lists)
    ]
    result["plugins"] = [
        _validate_download_item(item, "plugins", index)
        for index, item in enumerate(plugins)
    ]
    result["picons"] = [
        _validate_download_item(item, "picons", index)
        for index, item in enumerate(picons)
    ]

    oscam = data.get("oscam_dvbapi")
    if oscam is not None:
        result["oscam_dvbapi"] = _validate_download_item(
            oscam, "oscam_dvbapi", 0
        )
    else:
        result["oscam_dvbapi"] = None

    plugin_update = data.get("plugin_update")
    if plugin_update is not None:
        result["plugin_update"] = _validate_download_item(
            plugin_update, "plugin_update", 0
        )
    else:
        result["plugin_update"] = None
    return result


def parse_manifest(raw):
    """Parsuje tekst lub bajty JSON i waliduje manifest."""

    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
    except (UnicodeDecodeError, TypeError, ValueError) as exc:
        raise ManifestError("Nie można odczytać manifestu JSON: %s" % exc)
    return normalize_manifest(data)


def sha256_file(path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path, expected):
    expected = validate_sha256(expected)
    return sha256_file(path) == expected


def _safe_archive_name(name):
    """Zwraca znormalizowaną nazwę względną albo zgłasza ArchiveError."""

    if not isinstance(name, str) or not name:
        raise ArchiveError("Archiwum zawiera pustą nazwę pliku.")
    # Archiwa pochodzą z zewnętrznego repozytorium. Nie pozwalamy na ścieżki
    # absolutne, traversal ani backslashe mogące zmienić znaczenie na Windows.
    if "\\" in name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise ArchiveError("Niedozwolona ścieżka w archiwum: %s" % name)
    normalized = posixpath.normpath(name)
    if normalized in ("", ".") or normalized == ".." or normalized.startswith("../"):
        raise ArchiveError("Niedozwolona ścieżka w archiwum: %s" % name)
    return normalized


def _safe_target(root, relative_name):
    relative_name = _safe_archive_name(relative_name)
    root = os.path.realpath(root)
    target = os.path.realpath(os.path.join(root, *relative_name.split("/")))
    try:
        inside = os.path.commonpath((root, target)) == root
    except ValueError:
        inside = False
    if not inside:
        raise ArchiveError("Archiwum wychodzi poza katalog docelowy: %s" % relative_name)
    return target


def _extract_tar(archive_path, destination, max_total_bytes):
    extracted_bytes = 0
    with tarfile.open(archive_path, mode="r:*") as archive:
        members = archive.getmembers()
        for member in members:
            target = _safe_target(destination, member.name)
            if member.isdir():
                os.makedirs(target, exist_ok=True)
                continue
            if not member.isreg():
                raise ArchiveError("Niedozwolony typ wpisu w archiwum: %s" % member.name)
            extracted_bytes += member.size
            if extracted_bytes > max_total_bytes:
                raise ArchiveError("Archiwum przekracza limit rozpakowania.")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ArchiveError("Nie można odczytać pliku z archiwum: %s" % member.name)
            with source, open(target, "wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)


def _zip_is_symlink(info):
    mode = (info.external_attr >> 16) & 0o170000
    return stat.S_ISLNK(mode)


def _extract_zip(archive_path, destination, max_total_bytes):
    extracted_bytes = 0
    with zipfile.ZipFile(archive_path, mode="r") as archive:
        for info in archive.infolist():
            target = _safe_target(destination, info.filename)
            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            if _zip_is_symlink(info):
                raise ArchiveError("Archiwum ZIP zawiera dowiązanie: %s" % info.filename)
            extracted_bytes += info.file_size
            if extracted_bytes > max_total_bytes:
                raise ArchiveError("Archiwum przekracza limit rozpakowania.")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.open(info, "r") as source, open(target, "wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)


def extract_archive(archive_path, destination, max_total_bytes=256 * 1024 * 1024):
    """Bezpiecznie rozpakowuje tar(.gz/.bz2/.xz) lub ZIP do destination."""

    os.makedirs(destination, exist_ok=True)
    lower_name = archive_path.lower()
    if lower_name.endswith((".zip",)):
        _extract_zip(archive_path, destination, max_total_bytes)
    else:
        try:
            _extract_tar(archive_path, destination, max_total_bytes)
        except (tarfile.TarError, OSError) as exc:
            raise ArchiveError("Nie można rozpakować archiwum: %s" % exc)


def is_picon_file_name(name):
    """Rozpoznaje wyłącznie grafiki picon w formacie PNG."""

    return os.path.basename(str(name or "")).lower().endswith(".png")


def find_picon_files(root):
    """Znajduje picony w katalogu staging, bez zapisywania innych plików."""

    found = []
    for current_root, _directories, files in os.walk(root):
        for filename in files:
            if is_picon_file_name(filename):
                found.append(os.path.join(current_root, filename))
    return sorted(found)


def is_channel_file_name(name):
    name = os.path.basename(name).lower()
    if name in CHANNEL_FILE_NAMES:
        return True
    return name.startswith("userbouquet.") and name.endswith((".tv", ".radio"))


def find_channel_files(root):
    """Znajduje wyłącznie pliki należące do listy kanałów."""

    found = []
    for current_root, _directories, files in os.walk(root):
        for filename in files:
            if is_channel_file_name(filename):
                found.append(os.path.join(current_root, filename))
    return sorted(found)


def atomic_copy(source, destination):
    """Kopiuje plik atomowo w obrębie systemu plików."""

    destination = os.path.abspath(destination)
    parent = os.path.dirname(destination)
    os.makedirs(parent, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".%s." % os.path.basename(destination), dir=parent)
    os.close(fd)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
