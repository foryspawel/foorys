# -*- coding: utf-8 -*-

"""Mała warstwa zgodności dla obrazów Enigma2 z Pythonem 2.7 i 3.x."""

from __future__ import absolute_import

import io
import os
import shutil


try:  # pragma: no cover - wykonywane tylko na Pythonie 2
    text_type = unicode
    binary_type = str
    string_types = (basestring,)
except NameError:  # Python 3
    text_type = str
    binary_type = bytes
    string_types = (str,)


def to_text(value, encoding="utf-8", errors="replace"):
    """Zwraca tekst Unicode bez zależności od wersji Pythona."""

    if value is None:
        return text_type("")
    if isinstance(value, text_type):
        return value
    if isinstance(value, binary_type):
        return value.decode(encoding, errors)
    try:
        return text_type(value)
    except Exception:
        return text_type(repr(value))


def open_text(path, mode="r", errors="strict", newline=None):
    """Otwiera plik UTF-8 tak samo na Pythonie 2.7 i 3.x."""

    return io.open(path, mode, encoding="utf-8", errors=errors, newline=newline)


def ensure_dir(path):
    """Tworzy katalog bez wymagania parametru exist_ok z Pythona 3."""

    if not path:
        return path
    try:
        os.makedirs(path)
    except OSError:
        if not os.path.isdir(path):
            raise
    return path


def replace_file(source, destination):
    """Atomowo podmienia plik; na starym Pythonie używa rename na Linuksie."""

    replace = getattr(os, "replace", None)
    if replace is not None:
        replace(source, destination)
        return
    if os.name == "nt" and os.path.exists(destination):  # pragma: no cover
        os.unlink(destination)
    os.rename(source, destination)


def is_path_within(root, target):
    """Sprawdza containment ścieżki bez os.path.commonpath z Pythona 3."""

    root = os.path.normcase(os.path.realpath(root))
    target = os.path.normcase(os.path.realpath(target))
    return target == root or target.startswith(root.rstrip(os.sep) + os.sep)


def which(program):
    """Zamiennik shutil.which dostępny również w Pythonie 2.7."""

    native = getattr(shutil, "which", None)
    if native is not None:
        return native(program)
    directory, _name = os.path.split(program)
    if directory:
        return program if os.path.isfile(program) and os.access(program, os.X_OK) else None
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory.strip('"'), program)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None
