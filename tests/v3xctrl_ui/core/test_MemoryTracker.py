import unittest
from unittest.mock import MagicMock, patch

from v3xctrl_ui.core.MemoryTracker import MemoryTracker


class TestMemoryTracker(unittest.TestCase):
    def setUp(self):
        # Patch tracemalloc to avoid real snapshots
        self.patcher_tm = patch("v3xctrl_ui.core.MemoryTracker.tracemalloc")
        self.mock_tm = self.patcher_tm.start()

        # Fake snapshot with filter_traces and compare_to
        fake_snapshot = MagicMock()
        fake_snapshot.filter_traces.return_value = fake_snapshot
        fake_snapshot.compare_to.return_value = [f"stat{i}" for i in range(3)]

        self.mock_tm.take_snapshot.return_value = fake_snapshot

        # Patch time.sleep to immediately trigger stop
        self.patcher_sleep = patch(
            "v3xctrl_ui.core.MemoryTracker.time.sleep", side_effect=lambda _: self.mt._stop_event.set()
        )
        self.mock_sleep = self.patcher_sleep.start()

        self.mt = MemoryTracker(interval=1, top=2, enable_log=True)

    def tearDown(self):
        self.patcher_tm.stop()
        self.patcher_sleep.stop()

    def test_start_and_stop(self):
        self.mt.start()
        self.mt.stop()
        self.assertFalse(self.mt._thread.is_alive())

    def test_run_with_logging(self):
        self.mt.enable_log = True
        with patch("v3xctrl_ui.core.MemoryTracker.logger") as mock_logger:
            self.mt.start()
            self.mt._thread.join()
        mock_logger.debug.assert_any_call("Top 2 memory growth lines since last snapshot:")

    def test_run_without_logging(self):
        self.mt.enable_log = False
        with patch("v3xctrl_ui.core.MemoryTracker.logger") as mock_logger:
            self.mt.start()
            self.mt._thread.join()
        mock_logger.debug.assert_not_called()


if __name__ == "__main__":
    unittest.main()
