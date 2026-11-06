import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs

with patch("sys.argv", ["run.py"]):
    import run
from tools import exploit_set_global_enable as fallback


class SSHFallbackTests(unittest.TestCase):
    def setUp(self):
        self.router = Mock(ip="192.168.31.1", stok="token")

    def attempt(self, ports, result=True, error=None):
        with patch.object(run, "test_port", side_effect=ports), \
                patch.object(run.time, "sleep"), \
                patch.object(run, "detect_local_ip", return_value="192.168.31.2"), \
                patch.object(run, "enable_ssh_global", return_value=result,
                             side_effect=error) as second:
            outcome = run.enable_ssh_auto(self.router)
        return outcome, second

    def test_already_open_skips_both(self):
        outcome, second = self.attempt([True])
        self.assertTrue(outcome)
        self.router.inject.assert_not_called()
        second.assert_not_called()

    def test_first_success_skips_second(self):
        outcome, second = self.attempt([False, True])
        self.assertTrue(outcome)
        self.router.inject.assert_called_once()
        second.assert_not_called()

    def test_first_exception_still_falls_back(self):
        self.router.inject.side_effect = RuntimeError("timeout")
        outcome, second = self.attempt([False] * 5)
        self.assertTrue(outcome)
        second.assert_called_once()

    def test_both_fail(self):
        outcome, _ = self.attempt([False] * 5, result=False)
        self.assertFalse(outcome)

    def test_server_failure_reports_failure(self):
        outcome, _ = self.attempt([False] * 5, error=OSError("bind"))
        self.assertFalse(outcome)

    def test_stage_request_and_cleanup(self):
        server, thread, fetched = Mock(), Mock(), Mock()
        server.server_address = ("192.168.31.2", 8123)
        self.router.post.side_effect = RuntimeError("request timeout")
        with patch.object(fallback, "start_server", return_value=(server, thread, fetched)):
            self.assertTrue(fallback.enable_ssh(
                self.router, ["id"], "192.168.31.2", Mock(return_value=True)))
        route, body = self.router.post.call_args[0]
        self.assertEqual(route, fallback.ROUTE)
        params = parse_qs(body)
        self.assertEqual(params["enable"], ["1"])
        payload = params["mac"][0]
        self.assertIn("HTTP://192.168.31.2:8123/S", payload)
        self.assertEqual(payload.upper(), payload.replace("x", "X", 1))
        self.assertNotIn(";", payload)
        server.shutdown.assert_called_once()
        server.server_close.assert_called_once()
        thread.join.assert_called_once()

    def test_api_success_is_not_ssh_success(self):
        server, thread, fetched = Mock(), Mock(), Mock()
        server.server_address = ("192.168.31.2", 8123)
        self.router.post.return_value.text = '{"code":0}'
        with patch.object(fallback, "start_server", return_value=(server, thread, fetched)):
            self.assertFalse(fallback.enable_ssh(
                self.router, ["id"], "192.168.31.2", Mock(return_value=False), wait=0))

    def test_requires_login(self):
        self.router.stok = None
        with self.assertRaises(ValueError):
            fallback.enable_ssh(self.router, [], "192.168.31.2", Mock())

    def test_persistence_uses_known_global_enable(self):
        run.ctx.exploit_method = "global_enable"
        with patch.object(run, "persist_global", return_value=True) as mock_global, \
                patch.object(run, "detect_local_ip", return_value="192.168.31.2"):
            outcome = run.apply_persistence_auto(self.router)
        self.assertTrue(outcome)
        mock_global.assert_called_once()
        self.router.inject.assert_not_called()

    def test_persistence_uses_known_macfilter(self):
        run.ctx.exploit_method = "macfilter"
        self.router.inject.return_value = '{"code":0}'
        with patch.object(run, "test_port", return_value=True):
            outcome = run.apply_persistence_auto(self.router)
        self.assertTrue(outcome)
        self.router.inject.assert_called_once()

    def test_persistence_falls_back_to_global_enable(self):
        run.ctx.exploit_method = None
        self.router.inject.side_effect = RuntimeError("timeout")
        with patch.object(run, "test_port", return_value=False), \
                patch.object(run.time, "sleep"), \
                patch.object(run, "detect_local_ip", return_value="192.168.31.2"), \
                patch.object(run, "persist_global", return_value=True) as mock_global:
            outcome = run.apply_persistence_auto(self.router)
        self.assertTrue(outcome)
        self.router.inject.assert_called_once()
        mock_global.assert_called_once()
        self.assertEqual(run.ctx.exploit_method, "global_enable")

    def test_apply_persistence_server_and_cleanup(self):
        server, thread, fetched = Mock(), Mock(), Mock()
        server.server_address = ("192.168.31.2", 8123)
        fetched.is_set.return_value = True
        self.router.post.return_value.text = '{"code":0}'
        with patch.object(fallback, "start_server", return_value=(server, thread, fetched)):
            self.assertTrue(fallback.apply_persistence(
                self.router, "echo persist", "192.168.31.2", wait=0.1))
        server.shutdown.assert_called_once()
        server.server_close.assert_called_once()
        thread.join.assert_called_once()


if __name__ == "__main__":
    unittest.main()
