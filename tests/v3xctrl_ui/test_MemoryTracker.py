import unittest
from unittest.mock import MagicMock, patch

from src.v3xctrl_ui.MemoryTracker import MemoryTracker


class TestMemoryTracker(unittest.TestCase):
    def setUp(self):
        # Patch tracemalloc to avoid real snapshots
        self.patcher_tm = patch("src.v3xctrl_ui.MemoryTracker.tracemalloc")
        self.mock_tm = self.patcher_tm.start()

        # Fake snapshot with filter_traces and compare_to
        fake_snapshot = MagicMock()
        fake_snapshot.filter_traces.return_value = fake_snapshot
        fake_snapshot.compare_to.return_value = [f"stat{i}" for i in range(3)]

        self.mock_tm.take_snapshot.return_value = fake_snapshot

        # Patch time.sleep to immediately trigger stop
        self.patcher_sleep = patch("src.v3xctrl_ui.MemoryTracker.time.sleep", side_effect=lambda _: self.mt._stop_event.set())
        self.mock_sleep = self.patcher_sleep.start()

        self.mt = MemoryTracker(interval=1, top=2, enable_log=True)

    def tearDown(self):
        self.patcher_tm.stop()
        self.patcher_sleep.stop()

    def test_start_and_stop(self):
        # Thread should start and then be stopped cleanly
        self.mt.start()
        self.assertTrue(self.mt._thread.is_alive())
        self.mt.stop()
        self.assertFalse(self.mt._thread.is_alive())

    def test_run_with_logging(self):
        # Ensure prints happen when enable_log is True
        self.mt.enable_log = True
        with patch("builtins.print") as mock_print:
            self.mt.start()
            self.mt._thread.join()
        mock_print.assert_any_call("[MemoryTracker] Top 2 memory growth lines since last snapshot:")

    def test_run_without_logging(self):
        self.mt.enable_log = False
        with patch("builtins.print") as mock_print:
            self.mt.start()
            self.mt._thread.join()
        mock_print.assert_not_called()


if __name__ == "__main__":
    unittest.main()
