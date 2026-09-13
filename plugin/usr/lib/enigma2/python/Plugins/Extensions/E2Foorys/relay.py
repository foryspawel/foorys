# -*- coding: utf-8 -*-

"""Bezpieczny klient Foorys Relay i agent zadań w tle.

Dekoder zawsze inicjuje połączenie wychodzące. Relay nie przyjmuje haseł root
i nie wykonuje dowolnych poleceń shell — obsługiwane są wyłącznie akcje z
poniższej białej listy.
"""

from __future__ import absolute_import

import hashlib
import json
import os
import ssl
import threading
import time

try:
    from urllib.parse import urlparse
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover - stare obrazy E2 z Pythonem 2.7
    from urllib2 import Request, urlopen
    from urlparse import urlparse

from .compat import string_types, to_text
from .config import ensure_config, save_config, settings_dict
from .core import version_is_newer
from .operations import (
    collect_system_status,
    diagnose_internet_speed,
    diagnose_network,
    fetch_manifest,
    install_channel_list,
    install_current_oscam_dvbapi,
    install_e2iplayer,
    install_iptv_playlist,
    install_oscam_stable,
    install_picons,
    install_plugin_package,
    install_public_softcam,
)
from .version import VERSION

try:
    from enigma import eTimer
except ImportError:  # pragma: no cover - testy lokalne poza dekoderem
    eTimer = None


class RelayError(RuntimeError):
    """Błąd połączenia lub nieprawidłowej operacji Relay."""


USER_AGENT = "E2-Foorys-Relay/%s" % VERSION
REQUEST_LIMIT = 512 * 1024
POLL_SECONDS = 20
HEARTBEAT_SECONDS = 60


def _safe_error(error):
    code = getattr(error, "code", None)
    if code:
        return "serwer zwrócił HTTP %s" % code
    reason = getattr(error, "reason", None)
    if reason:
        return "brak połączenia (%s)" % to_text(reason)
    return to_text(error) or "brak połączenia z Relay"


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


def _redact(value, settings=None):
    """Usuwa dane logowania przed wysłaniem wyniku do panelu Relay."""

    text = to_text(value or "")
    settings = settings or {}
    for key in ("iptv_password", "iptv_username", "relay_device_token", "relay_pairing_code"):
        secret = to_text(settings.get(key, ""))
        if secret:
            text = text.replace(secret, "[ukryte]")
    return text[:1800]


def _ssl_context(expected_fingerprint):
    """Tworzy kontekst TLS; przy pinie certyfikatu weryfikacja jest lokalna."""

    if expected_fingerprint:
        creator = getattr(ssl, "_create_unverified_context", None)
        if creator is not None:
            return creator()
    creator = getattr(ssl, "create_default_context", None)
    if creator is not None:
        return creator()
    return None


def _peer_certificate(response):
    """Pobiera certyfikat TLS z kilku wariantów urllib/OpenSSL."""

    file_object = getattr(response, "fp", None)
    raw = getattr(file_object, "raw", None)
    sock = getattr(raw, "_sock", None)
    if sock is None:
        sock = getattr(file_object, "_sock", None)
    getter = getattr(sock, "getpeercert", None)
    if getter is None:
        return b""
    try:
        return getter(binary_form=True) or b""
    except (TypeError, OSError):
        return b""


def _open(request, timeout, expected_fingerprint=""):
    parsed = urlparse(request.get_full_url())
    context = _ssl_context(expected_fingerprint) if parsed.scheme.lower() == "https" else None
    try:
        if context is not None:
            response = urlopen(request, timeout=timeout, context=context)
        else:
            response = urlopen(request, timeout=timeout)
    except TypeError:  # urllib2 / starsze Python bez parametru context
        response = urlopen(request, timeout=timeout)
    if expected_fingerprint and parsed.scheme.lower() == "https":
        certificate = _peer_certificate(response)
        if not certificate:
            try:
                response.close()
            except Exception:
                pass
            raise RelayError("Nie można zweryfikować certyfikatu Foorys Relay.")
        actual = hashlib.sha256(certificate).hexdigest().lower()
        if actual != expected_fingerprint.lower():
            try:
                response.close()
            except Exception:
                pass
            raise RelayError("Certyfikat Foorys Relay nie zgadza się z zapisanym odciskiem.")
    return response


def _read_response(response):
    chunks = []
    total = 0
    while True:
        chunk = response.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > REQUEST_LIMIT:
            raise RelayError("Odpowiedź Relay jest za duża.")
        chunks.append(chunk)
    return b"".join(chunks)


class RelayClient(object):
    """Minimalny klient HTTP(S) dla API urządzenia Relay."""

    def __init__(self, settings):
        base_url = _setting(settings, "relay_url", "")
        parsed = urlparse(base_url)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            raise RelayError("Ustaw poprawny adres Foorys Relay (HTTP lub HTTPS).")
        if parsed.username or parsed.password:
            raise RelayError("Adres Relay nie może zawierać loginu ani hasła.")
        self.base_url = base_url.rstrip("/")
        self.device_id = _setting(settings, "relay_device_id", "")
        self.token = _setting(settings, "relay_device_token", "")
        self.fingerprint = _setting(settings, "relay_cert_sha256", "")

    def _request(self, path, method="GET", payload=None, timeout=20, device_auth=True):
        url = self.base_url + "/" + path.lstrip("/")
        headers = {"User-Agent": USER_AGENT, "Cache-Control": "no-cache"}
        if device_auth and self.token:
            headers["X-Foorys-Device-Token"] = self.token
        data = None
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers)
        if data is None and method != "GET":
            try:
                request.get_method = lambda: method
            except Exception:
                pass
        response = None
        try:
            response = _open(request, timeout, self.fingerprint)
            raw = _read_response(response)
        except RelayError:
            raise
        except Exception as error:
            raise RelayError(_safe_error(error))
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
        try:
            value = json.loads(to_text(raw)) if raw else {}
        except (TypeError, ValueError):
            raise RelayError("Relay zwrócił nieprawidłową odpowiedź.")
        if isinstance(value, dict) and value.get("error"):
            raise RelayError(to_text(value.get("error")))
        return value

    def register(self, pairing_code, name):
        if not pairing_code:
            raise RelayError("Wpisz kod parowania wygenerowany w panelu Foorys Relay.")
        result = self._request(
            "/v1/device/register",
            method="POST",
            payload={"pairingCode": pairing_code, "name": name or "Foorys dekoder"},
            timeout=20,
            device_auth=False,
        )
        if not result.get("deviceId") or not result.get("deviceToken"):
            raise RelayError("Relay nie zwrócił danych nowego urządzenia.")
        return result

    def heartbeat(self, metrics):
        return self._request(
            "/v1/device/heartbeat",
            method="POST",
            payload={"metrics": metrics or {}},
            timeout=25,
        )

    def jobs(self):
        return self._request("/v1/device/jobs", timeout=25).get("jobs", [])

    def result(self, job_id, ok, message):
        return self._request(
            "/v1/device/jobs/%s/result" % to_text(job_id),
            method="POST",
            payload={"ok": bool(ok), "message": _redact(message)},
            timeout=25,
        )


def _manifest(settings, progress=None):
    _progress(progress, "Pobieram centralny katalog Foorys...")
    url = _setting(settings, "manifest_url", "")
    if not url:
        raise RelayError("Brak adresu centralnego katalogu Foorys.")
    try:
        return fetch_manifest(url)
    except Exception as error:
        raise RelayError("Nie udało się pobrać katalogu: %s" % _safe_error(error))


def _find_entry(manifest, collection, entry_id="", prefix=""):
    entries = manifest.get(collection, []) if isinstance(manifest, dict) else []
    entry_id = to_text(entry_id or "")
    prefix = to_text(prefix or "")
    for entry in entries:
        candidate = to_text(entry.get("id", ""))
        if entry_id and candidate == entry_id:
            return entry
        if prefix and candidate.startswith(prefix):
            return entry
    return None


def _status_summary(data):
    memory = data.get("memory", {})
    flash = data.get("flash", {})
    return (
        "Stan dekodera Foorys\n"
        "Model: %s\n"
        "Obraz: %s %s\n"
        "CPU: %s%%   RAM: %s%%\n"
        "RootFS wolne: %s\n"
        "Temperatura: %s\n"
        "Enigma2: %s"
        % (
            data.get("model", "n/d"),
            data.get("image", "n/d"),
            data.get("version", "n/d"),
            data.get("cpu_percent", 0),
            memory.get("percent", 0),
            _human_size(flash.get("free", 0)),
            data.get("temperature", "n/d"),
            "OK" if data.get("enigma2_running") else "n/p",
        )
    )


def _human_size(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/d"
    units = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while abs(number) >= 1024 and index < len(units) - 1:
        number /= 1024.0
        index += 1
    return "%.1f %s" % (number, units[index])


def _operation_result(result):
    if not isinstance(result, dict):
        return to_text(result)
    if result.get("summary"):
        return result.get("summary")
    if result.get("kind") == "channels":
        return "Lista kanałów zainstalowana. Pliki: %s" % ", ".join(result.get("installed", []))
    if result.get("kind") == "iptv":
        return "Foorys IPTV zainstalowany. Kanały: %s, bukiet: %s" % (result.get("channels", 0), result.get("bouquet", "n/d"))
    if result.get("kind") == "picons":
        return "Picony zaktualizowane. Plików: %s" % result.get("installed_count", 0)
    if result.get("kind") == "oscam.dvbapi":
        return "oscam.dvbapi zaktualizowany: %s" % result.get("target", "n/d")
    if result.get("output"):
        return to_text(result.get("output"))[-1500:]
    return "Operacja zakończona pomyślnie."


def execute_remote_action(action, params, settings, progress=None):
    """Wykonuje jedną akcję otrzymaną z Relay po białej liście."""

    action = to_text(action or "")
    params = params if isinstance(params, dict) else {}
    if action == "status":
        status = collect_system_status(settings)
        return {"kind": "relay-status", "ok": True, "summary": _status_summary(status), "metrics": status}
    if action == "diagnostics":
        status = collect_system_status(settings)
        network = diagnose_network(None, settings, progress)
        return {"kind": "relay-diagnostics", "ok": bool(network.get("ok")), "summary": "%s\n\n%s" % (_status_summary(status), network.get("summary", ""))}
    if action == "network_diagnostic":
        return diagnose_network(None, settings, progress)
    if action == "speed_test":
        return diagnose_internet_speed(None, settings, progress)
    if action == "refresh_catalog":
        manifest = _manifest(settings, progress)
        return {"kind": "relay-catalog", "ok": True, "summary": "Katalog odświeżony: %d list, %d pluginów, %d pakietów piconów." % (len(manifest.get("channel_lists", [])), len(manifest.get("plugins", [])), len(manifest.get("picons", [])))}
    if action == "install_foorys_channels":
        manifest = _manifest(settings, progress)
        item = _find_entry(manifest, "channel_lists", prefix="foorys-hotbird")
        if not item:
            raise RelayError("Brak listy Foorys Hotbird 13E w centralnym katalogu.")
        return install_channel_list(item, settings, progress)
    if action == "install_bzyk83_hotbird":
        manifest = _manifest(settings, progress)
        item = _find_entry(manifest, "channel_lists", prefix="bzyk83-hotbird")
        if not item:
            raise RelayError("Brak listy Bzyk83 Hotbird w centralnym katalogu.")
        return install_channel_list(item, settings, progress)
    if action == "install_bzyk83_dual":
        manifest = _manifest(settings, progress)
        item = _find_entry(manifest, "channel_lists", prefix="bzyk83-dual")
        if not item:
            raise RelayError("Brak listy Bzyk83 Dual w centralnym katalogu.")
        return install_channel_list(item, settings, progress)
    if action == "install_channel":
        manifest = _manifest(settings, progress)
        item = _find_entry(manifest, "channel_lists", entry_id=params.get("id"))
        if not item:
            raise RelayError("Wybranej listy kanałów nie ma w centralnym katalogu.")
        return install_channel_list(item, settings, progress)
    if action == "install_foorys_iptv":
        return install_iptv_playlist({}, settings, progress)
    if action == "install_picons_hotbird":
        manifest = _manifest(settings, progress)
        item = _find_entry(manifest, "picons", prefix="chocholousek-220x132-13.0e")
        if not item:
            raise RelayError("Brak piconów Hotbird 13E w centralnym katalogu.")
        return install_picons(item, settings, progress)
    if action == "install_picons":
        manifest = _manifest(settings, progress)
        item = _find_entry(manifest, "picons", entry_id=params.get("id"))
        if not item:
            raise RelayError("Wybranych piconów nie ma w centralnym katalogu.")
        return install_picons(item, settings, progress)
    if action == "install_plugin":
        manifest = _manifest(settings, progress)
        item = _find_entry(manifest, "plugins", entry_id=params.get("id"))
        if not item:
            raise RelayError("Wybranego pluginu nie ma w centralnym katalogu.")
        return install_plugin_package(item, settings, progress)
    if action == "install_xstreamity":
        manifest = _manifest(settings, progress)
        item = _find_entry(manifest, "plugins", entry_id="xstreamity")
        if not item:
            raise RelayError("XStreamity nie jest opublikowany w katalogu.")
        return install_plugin_package(item, settings, progress)
    if action == "install_chocholousek":
        manifest = _manifest(settings, progress)
        item = _find_entry(manifest, "plugins", entry_id="chocholousek-picons")
        if not item:
            raise RelayError("Plugin Chocholousek Picons nie jest opublikowany w katalogu.")
        return install_plugin_package(item, settings, progress)
    if action == "install_e2iplayer":
        return install_e2iplayer({}, settings, progress)
    if action == "install_oscam_stable":
        return install_oscam_stable({}, settings, progress)
    if action in ("install_oscam_emu", "install_ncam", "install_cccam"):
        ids = {"install_oscam_emu": "oscam-emu", "install_ncam": "ncam", "install_cccam": "cccam-2.3.9"}
        return install_public_softcam({"id": ids[action]}, settings, progress)
    if action == "oscam_dvbapi":
        return install_current_oscam_dvbapi({}, settings, progress)
    if action == "update_plugin":
        manifest = _manifest(settings, progress)
        item = manifest.get("plugin_update")
        if not item:
            raise RelayError("Brak aktualizacji E2-Foorys w centralnym katalogu.")
        if not version_is_newer(item.get("version"), VERSION):
            return {"kind": "relay-update", "ok": True, "summary": "E2-Foorys jest aktualny (%s)." % VERSION}
        return install_plugin_package(item, settings, progress)
    raise RelayError("Akcja Relay nie jest dozwolona.")


def pair_relay(_item, settings, progress=None):
    """Jednorazowo rejestruje dekoder kodem z panelu administratora."""

    client = RelayClient(settings)
    _progress(progress, "Łączę dekoder z Foorys Relay...")
    result = client.register(
        _setting(settings, "relay_pairing_code", ""),
        _setting(settings, "relay_device_name", "Foorys dekoder"),
    )
    section = ensure_config()
    section.relay_device_id.value = to_text(result.get("deviceId"))
    section.relay_device_token.value = to_text(result.get("deviceToken"))
    section.relay_pairing_code.value = ""
    save_config()
    _progress(progress, "Dekoder został sparowany; token zapisano lokalnie.")
    return {"kind": "relay-pair", "ok": True, "name": "Foorys Relay", "device_id": result.get("deviceId"), "summary": "Dekoder został sparowany z Foorys Relay. Połączenie będzie działać automatycznie w tle."}


def check_relay(_item, settings, progress=None):
    """Wysyła bieżący heartbeat i sprawdza połączenie urządzenia."""

    if not _setting(settings, "relay_device_token", "") or not _setting(settings, "relay_device_id", ""):
        raise RelayError("Ten dekoder nie jest jeszcze sparowany z Foorys Relay.")
    _progress(progress, "Wysyłam test stanu do Foorys Relay...")
    client = RelayClient(settings)
    status = collect_system_status(settings)
    client.heartbeat(status)
    return {"kind": "relay-check", "ok": True, "name": "Foorys Relay", "summary": "Połączenie z Foorys Relay działa. Ostatni stan dekodera został wysłany."}


class RelayAgent(object):
    """Demon wątku pluginu: heartbeat i pobieranie zadań bez portu na dekoderze."""

    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None
        self.session = None
        self.dispatch_timer = None
        self.restart_requested = False
        self.last_error = ""
        self.last_success = 0

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        if self.running:
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.dispatch_timer is not None:
            try:
                self.dispatch_timer.stop()
            except Exception:
                pass

    def attach_session(self, session):
        self.session = session
        if self.dispatch_timer is None and eTimer is not None:
            self.dispatch_timer = eTimer()
            try:
                self.dispatch_timer.callback.append(self._dispatch)
            except AttributeError:
                self.dispatch_timer.timeout.get().append(self._dispatch)
        if self.dispatch_timer is not None:
            self.dispatch_timer.start(1000, True)

    def detach_session(self):
        self.session = None
        if self.dispatch_timer is not None:
            try:
                self.dispatch_timer.stop()
            except Exception:
                pass

    def _dispatch(self):
        if self.restart_requested and self.session is not None:
            self.restart_requested = False
            try:
                from Screens.Standby import TryQuitMainloop

                self.session.open(TryQuitMainloop, 3)
            except Exception:
                self.last_error = "Nie udało się uruchomić restartu GUI."
        if self.dispatch_timer is not None and self.session is not None and not self.stop_event.is_set():
            self.dispatch_timer.start(1000, True)

    def _wait(self, seconds):
        self.stop_event.wait(seconds)

    def _loop(self):
        next_heartbeat = 0
        while not self.stop_event.is_set():
            try:
                settings = settings_dict()
                if not settings.get("relay_enabled"):
                    self._wait(POLL_SECONDS)
                    continue
                if not settings.get("relay_device_id") or not settings.get("relay_device_token"):
                    self._wait(POLL_SECONDS)
                    continue
                client = RelayClient(settings)
                now = time.time()
                if now >= next_heartbeat:
                    metrics = collect_system_status(settings)
                    client.heartbeat(metrics)
                    next_heartbeat = now + HEARTBEAT_SECONDS
                jobs = client.jobs()
                for job in jobs:
                    if self.stop_event.is_set():
                        break
                    self._run_job(client, job, settings)
                self.last_error = ""
                self.last_success = int(time.time())
                self._wait(POLL_SECONDS)
            except Exception as error:
                self.last_error = to_text(error)
                self._wait(30)

    def _run_job(self, client, job, settings):
        job_id = job.get("id")
        action = job.get("action")
        try:
            if action == "restart_gui":
                self.restart_requested = True
                result = {"kind": "relay", "summary": "Restart GUI został zaplanowany na dekoderze."}
            else:
                result = execute_remote_action(action, job.get("params", {}), settings)
            client.result(job_id, True, _operation_result(result))
        except Exception as error:
            try:
                client.result(job_id, False, _redact(error, settings))
            except Exception as result_error:
                self.last_error = to_text(result_error)


_AGENT = None
_AGENT_LOCK = threading.Lock()


def get_agent():
    global _AGENT
    with _AGENT_LOCK:
        if _AGENT is None:
            _AGENT = RelayAgent()
        return _AGENT


def start_agent():
    get_agent().start()


def stop_agent():
    global _AGENT
    if _AGENT is not None:
        _AGENT.stop()

