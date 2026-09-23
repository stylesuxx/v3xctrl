import unittest

from v3xctrl_ui.core.dataclasses import ApplicationModel
from v3xctrl_ui.network.ControlSender import ControlSender


class TestControlSender(unittest.TestCase):
    def setUp(self):
        self.model = ApplicationModel()
        self.model.control_interval = 1 / 30
        self.model.user_connected = True
        self.sent: list[tuple[float, float]] = []
        self.sender = ControlSender(self.model, lambda throttle, steering: self.sent.append((throttle, steering)))

    def test_sends_the_latest_values_once_per_interval(self):
        """The render loop sets values whenever it runs; the sender's cadence is its own."""
        self.sender.set_values(0.2, 0.0)
        self.sender.set_values(0.5, -0.1)

        deadline = self.sender.run_once(now=100.0)

        self.assertEqual(self.sent, [(0.5, -0.1)])
        self.assertAlmostEqual(deadline, 100.0 + 1 / 30)

    def test_repeats_the_last_values_when_the_render_loop_falls_behind(self):
        self.sender.set_values(0.5, 0.0)

        self.sender.run_once(now=100.0)
        self.sender.run_once(now=100.0 + 1 / 30)

        self.assertEqual(self.sent, [(0.5, 0.0), (0.5, 0.0)])

    def test_sends_nothing_before_the_user_connected(self):
        self.model.user_connected = False
        self.sender.set_values(0.5, 0.0)

        self.sender.run_once(now=100.0)

        self.assertEqual(self.sent, [])

    def test_follows_a_changed_rate(self):
        self.model.control_interval = 1 / 60

        deadline = self.sender.run_once(now=100.0)

        self.assertAlmostEqual(deadline, 100.0 + 1 / 60)

    def test_thread_sends_at_the_rate_and_stops(self):
        import time

        self.model.control_interval = 0.01
        self.sender.set_values(0.1, 0.1)
        self.sender.start()
        time.sleep(0.12)
        self.sender.stop()
        self.sender.join(timeout=1.0)

        self.assertFalse(self.sender.is_alive())
        self.assertGreaterEqual(len(self.sent), 8)
        self.assertLessEqual(len(self.sent), 14)
