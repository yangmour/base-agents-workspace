import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import forward


class ForwardControlTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.state = Path(temp.name)
        self.enter(patch.object(forward, "STATE", self.state))
        self.enter(contextlib.redirect_stderr(io.StringIO()))

    def enter(self, manager):
        result = manager.__enter__()
        self.addCleanup(manager.__exit__, None, None, None)
        return result

    def run_control(self, *args):
        with patch.object(sys, "argv", ["forward.sh", *args]):
            return forward.main()

    def test_offline_restart_preserves_workers(self):
        with patch("forward.subprocess.run", side_effect=subprocess.TimeoutExpired("kubectl", 6)) as api, \
             patch("forward.stop") as stop, patch("forward.start") as start:
            self.assertEqual(1, self.run_control("restart"))
            self.assertEqual(api.call_args.kwargs["timeout"], 6)
            stop.assert_not_called()
            start.assert_not_called()

    def test_one_failure_does_not_skip_other_services_or_proxy(self):
        with patch("forward.subprocess.run"), patch("forward.start", side_effect=lambda n: n != "redis") as start:
            self.assertEqual(1, self.run_control("ensure"))
            self.assertEqual([c.args[0] for c in start.call_args_list], list(forward.PORTS))

    def test_proxy_waits_for_its_own_tunnel(self):
        with patch("forward.subprocess.run"), patch("forward.start", return_value=False) as start:
            self.assertEqual(1, self.run_control("ensure", "rocketmq"))
            start.assert_called_once_with("rocketmq")

    def test_scheduled_check_respects_stop_until_explicit_start(self):
        with patch("forward.subprocess.run"), patch("forward.start", return_value=True) as start, patch("forward.stop"):
            self.assertEqual(0, self.run_control("stop", "rocketmq"))
            self.assertEqual(0, self.run_control("periodic", "rocketmq"))
            start.assert_not_called()
            self.assertEqual(0, self.run_control("ensure", "rocketmq"))
            self.assertEqual([c.args[0] for c in start.call_args_list], ["rocketmq", "rocketmq-proxy"])

    def test_healthy_owned_tunnel_is_preserved(self):
        with patch("forward.owned", return_value=123), patch("forward.healthy", return_value=True), \
             patch("forward.listening", return_value=True), patch("forward.owns_listener", return_value=True), patch("forward.stop") as stop:
            self.assertTrue(forward.start("redis"))
            stop.assert_not_called()

    def test_foreign_listener_and_live_supervisor_are_not_reported_healthy(self):
        with patch("forward.owned", return_value=123), patch("forward.healthy", return_value=True), \
             patch("forward.owns_listener", return_value=False), patch("forward.listening", return_value=True), \
             patch("forward.stop") as stop:
            self.assertFalse(forward.start("redis"))
            stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
