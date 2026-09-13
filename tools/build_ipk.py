#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Buduje prosty pakiet .ipk z katalogu plugin/.

Przykład:
    python tools/build_ipk.py --version 0.1.0
"""

from __future__ import annotations

import argparse
import io
import os
import tarfile
import time


PACKAGE_NAME = "enigma2-plugin-extensions-e2foorys"


def _tar_bytes(source_dir, gzip=True):
    buffer = io.BytesIO()
    mode = "w:gz" if gzip else "w"
    with tarfile.open(fileobj=buffer, mode=mode) as archive:
        for root, directories, files in os.walk(source_dir):
            directories[:] = sorted(
                name for name in directories if name not in ("__pycache__", ".pytest_cache")
            )
            files[:] = sorted(
                name for name in files if not name.endswith((".pyc", ".pyo"))
            )
            for name in directories + files:
                path = os.path.join(root, name)
                arcname = os.path.relpath(path, source_dir).replace(os.sep, "/")
                archive.add(path, arcname=arcname, recursive=False)
    return buffer.getvalue()


def _ar_member(name, content):
    timestamp = int(time.time())
    header = "%-16s%-12d%-6d%-6d%-8o%-10d`\n" % (
        name,
        timestamp,
        0,
        0,
        0o100644,
        len(content),
    )
    encoded = header.encode("ascii")
    if len(encoded) != 60:
        raise RuntimeError("Nieprawidłowy nagłówek ar dla %s" % name)
    padding = b"\n" if len(content) % 2 else b""
    return encoded + content + padding


def build_ipk(plugin_root, output_path, version):
    data_root = os.path.join(plugin_root)
    if not os.path.isdir(data_root):
        raise RuntimeError("Brak katalogu plugin: %s" % data_root)
    control_text = (
        "Package: %s\n"
        "Version: %s\n"
        "Architecture: all\n"
        "Maintainer: Foorys\n"
        "Description: E2-Foorys - zarządzanie listami kanałów i pakietami\n"
        % (PACKAGE_NAME, version)
    ).encode("utf-8")
    control_root = os.path.join(os.path.dirname(output_path), ".ipk-control")
    os.makedirs(control_root, exist_ok=True)
    control_file = os.path.join(control_root, "control")
    with open(control_file, "wb") as handle:
        handle.write(control_text)
    control_tar = _tar_bytes(control_root)
    data_tar = _tar_bytes(data_root)

    output_parent = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_parent, exist_ok=True)
    with open(output_path, "wb") as package:
        package.write(b"!<arch>\n")
        package.write(_ar_member("debian-binary", b"2.0\n"))
        package.write(_ar_member("control.tar.gz", control_tar))
        package.write(_ar_member("data.tar.gz", data_tar))
    try:
        os.unlink(control_file)
        os.rmdir(control_root)
    except OSError:
        pass
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Buduj pakiet IPK E2-Foorys")
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--plugin-root", default="plugin")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    output = args.output or os.path.join(
        "dist", "%s_%s_all.ipk" % (PACKAGE_NAME, args.version)
    )
    print(build_ipk(args.plugin_root, output, args.version))


if __name__ == "__main__":
    main()
