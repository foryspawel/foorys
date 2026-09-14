import unittest
from unittest import mock

from plugin_loader import load_relay


relay = load_relay()


class _Response(object):
    def __init__(self, body):
        self.body = body
        self.closed = False

    def read(self, _limit):
        return self.body

    def close(self):
        self.closed = True


class RelayCaptchaTests(unittest.TestCase):
    def test_parse_tcp_listener_decodes_actual_lan_address(self):
        lines = [
            "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n",
            "   0: B112A8C0:2329 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 1 1 0000000000000000 100 0 0 10 0\n",
            "   1: 00000000:0050 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 2 1 0000000000000000 100 0 0 10 0\n",
        ]
        self.assertEqual(relay._parse_e2i_tcp_listeners(lines), [("192.168.18.177", 9001)])

    def test_extracts_e2i_target_embedded_in_javascript(self):
        html = 'window.location = "https://captcha.example/check#e2itcf_sep_c=session-123";'
        target, captcha_id = relay._e2i_target(html)
        self.assertEqual(target, "https://captcha.example/check#e2itcf_sep_c=session-123")
        self.assertEqual(captcha_id, "session-123")

    def test_prepare_uses_detected_listener_without_public_access(self):
        response = _Response(b'<a href="https://captcha.example/#e2itcf_sep_c=session-123">Open</a>')
        progress = []
        with mock.patch.object(relay, "_e2i_probe_endpoints", return_value=[("192.168.18.177", 9001)]), mock.patch.object(
            relay, "urlopen", return_value=response
        ) as open_mock:
            result = relay.prepare_e2i_capture({}, {}, progress.append)

        self.assertEqual(result["callbackUrl"], "http://192.168.18.177:9001/")
        self.assertEqual(result["captchaId"], "session-123")
        self.assertTrue(response.closed)
        self.assertEqual(open_mock.call_args[0][0].get_full_url(), "http://192.168.18.177:9001/")
        self.assertTrue(any("Znaleziono sesję" in item for item in progress))

    def test_console_rejects_unknown_command_and_returns_system_status(self):
        status = {
            "model": "H9 Twin",
            "image": "OpenATV",
            "version": "8.0",
            "cpu_percent": 12,
            "cpu_load_percent": 8,
            "memory": {"percent": 45},
            "flash": {"free": 1024, "total": 2048},
            "storage": {"free": 4096, "total": 8192},
            "uptime": 99,
            "enigma2_running": True,
        }
        with mock.patch.object(relay, "collect_system_status", return_value=status):
            result = relay.relay_console("system", {})
        self.assertTrue(result["ok"])
        self.assertIn("H9 Twin", result["summary"])
        with self.assertRaises(relay.RelayError):
            relay.relay_console("nieobsługiwane", {})


if __name__ == "__main__":
    unittest.main()
