"""Ładuje core.py bez importowania zależności Enigma2."""

import importlib.util
import os
import sys
import types


def load_core():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    package_name = "E2Foorys_test_package"
    package = types.ModuleType(package_name)
    package.__path__ = []
    sys.modules[package_name] = package
    path = os.path.join(
        root,
        "plugin",
        "usr",
        "lib",
        "enigma2",
        "python",
        "Plugins",
        "Extensions",
        "E2Foorys",
        "core.py",
    )
    spec = importlib.util.spec_from_file_location(package_name + ".core", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_operations():
    load_core()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    package_name = "E2Foorys_test_package"
    path = os.path.join(
        root,
        "plugin",
        "usr",
        "lib",
        "enigma2",
        "python",
        "Plugins",
        "Extensions",
        "E2Foorys",
        "operations.py",
    )
    spec = importlib.util.spec_from_file_location(package_name + ".operations", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
