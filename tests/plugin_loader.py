"""Ładuje core.py bez importowania zależności Enigma2."""

import importlib.util
import os
import sys
import types


def load_core():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    package_name = "E2Foorys_test_package"
    package_root = os.path.join(
        root,
        "plugin",
        "usr",
        "lib",
        "enigma2",
        "python",
        "Plugins",
        "Extensions",
        "E2Foorys",
    )
    package = types.ModuleType(package_name)
    package.__path__ = [package_root]
    sys.modules[package_name] = package
    path = os.path.join(package_root, "core.py")
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


def load_relay():
    """Ładuje relay.py z prostymi atrapami zależności Enigma2/operacji."""

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    package_name = "E2Foorys_relay_test_package"
    package_root = os.path.join(
        root,
        "plugin",
        "usr",
        "lib",
        "enigma2",
        "python",
        "Plugins",
        "Extensions",
        "E2Foorys",
    )
    package = types.ModuleType(package_name)
    package.__path__ = [package_root]
    sys.modules[package_name] = package

    config = types.ModuleType(package_name + ".config")
    config.ensure_config = lambda: None
    config.save_config = lambda: None
    config.settings_dict = lambda: {}
    sys.modules[config.__name__] = config

    core = types.ModuleType(package_name + ".core")
    core.version_is_newer = lambda _candidate, _installed: False
    sys.modules[core.__name__] = core

    operations = types.ModuleType(package_name + ".operations")
    for name in (
        "collect_system_status",
        "collect_installed_packages",
        "diagnose_internet_speed",
        "diagnose_network",
        "fetch_manifest",
        "install_channel_list",
        "install_current_oscam_dvbapi",
        "install_e2iplayer",
        "install_iptv_playlist",
        "install_oscam_stable",
        "install_picons",
        "install_plugin_package",
        "install_public_softcam",
    ):
        setattr(operations, name, lambda *_args, **_kwargs: {})
    sys.modules[operations.__name__] = operations

    version = types.ModuleType(package_name + ".version")
    version.VERSION = "test"
    sys.modules[version.__name__] = version

    path = os.path.join(package_root, "relay.py")
    spec = importlib.util.spec_from_file_location(package_name + ".relay", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
