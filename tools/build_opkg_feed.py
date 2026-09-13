#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Buduje indeks Packages/Packages.gz dla pakietów IPK w feedzie opkg."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import shutil
import tarfile


def _read_ar_members(path):
    with open(path, "rb") as handle:
        data = handle.read()
    if not data.startswith(b"!<arch>\n"):
        raise RuntimeError("Plik nie jest archiwum ar/IPK: %s" % path)
    offset = 8
    members = {}
    while offset + 60 <= len(data):
        header = data[offset:offset + 60]
        offset += 60
        name = header[0:16].decode("ascii", "replace").strip().rstrip("/")
        try:
            size = int(header[48:58].decode("ascii", "replace").strip())
        except ValueError:
            raise RuntimeError("Uszkodzony nagłówek ar w: %s" % path)
        content = data[offset:offset + size]
        if len(content) != size:
            raise RuntimeError("Niepełny element ar w: %s" % path)
        members[name] = content
        offset += size + (size % 2)
    return members


def _parse_control(text):
    fields = {}
    current = None
    for line in text.splitlines():
        if line[:1].isspace() and current:
            fields[current] += "\n" + line.strip()
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current = key.strip()
        fields[current] = value.strip()
    return fields


def _package_control(path):
    members = _read_ar_members(path)
    control_archive = members.get("control.tar.gz") or members.get("control.tar")
    if control_archive is None:
        raise RuntimeError("IPK nie zawiera control.tar: %s" % path)
    with tarfile.open(fileobj=io.BytesIO(control_archive), mode="r:*") as archive:
        control_member = None
        for member in archive.getmembers():
            if os.path.basename(member.name) == "control" and member.isfile():
                control_member = member
                break
        if control_member is None:
            raise RuntimeError("IPK nie zawiera pliku control: %s" % path)
        extracted = archive.extractfile(control_member)
        if extracted is None:
            raise RuntimeError("Nie można odczytać control w: %s" % path)
        return _parse_control(extracted.read().decode("utf-8", "replace"))


def _checksum(path, algorithm):
    digest = hashlib.new(algorithm)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _entry(path):
    control = _package_control(path)
    filename = os.path.basename(path)
    entry = {
        "Package": control.get("Package", ""),
        "Version": control.get("Version", ""),
        "Architecture": control.get("Architecture", "all"),
        "Maintainer": control.get("Maintainer", "Foorys"),
        "Section": control.get("Section", "extensions"),
        "Priority": control.get("Priority", "optional"),
        "Description": control.get("Description", ""),
        "Filename": filename,
        "Size": str(os.path.getsize(path)),
        "MD5Sum": _checksum(path, "md5"),
        "SHA256sum": _checksum(path, "sha256"),
    }
    if not entry["Package"] or not entry["Version"]:
        raise RuntimeError("IPK nie ma Package/Version: %s" % path)
    return entry


def _render(entries):
    blocks = []
    keys = (
        "Package",
        "Version",
        "Architecture",
        "Maintainer",
        "Section",
        "Priority",
        "Description",
        "Filename",
        "Size",
        "MD5Sum",
        "SHA256sum",
    )
    for entry in entries:
        lines = []
        for key in keys:
            value = entry.get(key, "")
            if not value:
                continue
            lines.append("%s: %s" % (key, value.replace("\n", "\n ")))
        blocks.append("\n".join(lines))
    return ("\n\n".join(blocks) + "\n") if blocks else ""


def build_feed(feed_dir, package_paths):
    os.makedirs(feed_dir, exist_ok=True)
    for source in package_paths:
        destination = os.path.join(feed_dir, os.path.basename(source))
        if os.path.abspath(source) != os.path.abspath(destination):
            shutil.copy2(source, destination)

    packages = []
    for filename in sorted(os.listdir(feed_dir)):
        if not filename.lower().endswith(".ipk"):
            continue
        packages.append(_entry(os.path.join(feed_dir, filename)))
    content = _render(packages).encode("utf-8")
    with open(os.path.join(feed_dir, "Packages"), "wb") as handle:
        handle.write(content)
    with gzip.GzipFile(os.path.join(feed_dir, "Packages.gz"), "wb", mtime=0) as handle:
        handle.write(content)
    return len(packages)


def main():
    parser = argparse.ArgumentParser(description="Buduj feed opkg dla pakietów IPK")
    parser.add_argument("--feed-dir", default="feed")
    parser.add_argument("packages", nargs="+", help="Ścieżki do pakietów IPK")
    args = parser.parse_args()
    count = build_feed(args.feed_dir, args.packages)
    print("Wygenerowano feed opkg: %d pakiet(ów)" % count)


if __name__ == "__main__":
    main()
