import logging
import time
import unittest
from unittest.mock import MagicMock, patch

from src.v3xctrl_helper.ntp import (
    NTPClock,
    get_ntp_offset_chrony,
    get_ntp_offset_ntplib,
)


class TestGetNtpOffsetChrony(unittest.TestCase):
    @patch("src.v3xctrl_helper.ntp.subprocess.run")
    def test_parses_chronyc_output(self, mock_run):
        # chronyc -c tracking CSV fields: ref_id, ip, stratum, ref_time, offset, ...
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="A29FC87B,time.cloudflare.com,3,1234567890.123,+0.000123456,0.000050,0.001\n",
            stderr="",
        )

        offset = get_ntp_offset_chrony()

        self.assertEqual(offset, 123)
        self.assertIsInstance(offset, int)
        mock_run.assert_called_once_with(["chronyc", "-c", "tracking"], capture_output=True, text=True, timeout=5)

    @patch("src.v3xctrl_helper.ntp.subprocess.run")
    def test_negative_offset(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="A29FC87B,server,3,1234567890.123,-0.000500000,0.000050,0.001\n", stderr=""
        )

        offset = get_ntp_offset_chrony()

        self.assertEqual(offset, -500)
        self.assertIsInstance(offset, int)

    @patch("src.v3xctrl_helper.ntp.subprocess.run")
    def test_raises_on_nonzero_exit(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="chronyc: command not found")

        with self.assertRaises(RuntimeError):
            get_ntp_offset_chrony()

    @patch("src.v3xctrl_helper.ntp.subprocess.run")
    def test_raises_on_unexpected_output(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="short,output", stderr="")

        with self.assertRaises(RuntimeError):
            get_ntp_offset_chrony()

    @patch("src.v3xctrl_helper.ntp.subprocess.run")
    def test_raises_on_timeout(self, mock_run):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="chronyc", timeout=5)

        with self.assertRaises(RuntimeError):
            get_ntp_offset_chrony()


class TestGetNtpOffsetNtplib(unittest.TestCase):
    @patch("ntplib.NTPClient")
    def test_queries_ntp_server(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.offset = 0.000250
        mock_client_class.return_value.request.return_value = mock_response

        offset = get_ntp_offset_ntplib()

        self.assertEqual(offset, 250)
        self.assertIsInstance(offset, int)
        mock_client_class.return_value.request.assert_called_once_with("pool.ntp.org", version=3, timeout=5)

    @patch("ntplib.NTPClient")
    def test_negative_offset(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.offset = -0.001000
        mock_client_class.return_value.request.return_value = mock_response

        offset = get_ntp_offset_ntplib()

        self.assertEqual(offset, -1000)
        self.assertIsInstance(offset, int)

    @patch("ntplib.NTPClient")
    def test_raises_on_failure(self, mock_client_class):
        mock_client_class.return_value.request.side_effect = Exception("timeout")

        with self.assertRaises(RuntimeError):
            get_ntp_offset_ntplib()


class TestNTPClock(unittest.TestCase):
    def _make_clock(self, offset_values=None):
        """Create an NTPClock with mocked offset function returning sequential values."""
        if offset_values is None:
            offset_values = [100]

        values = list(offset_values)

        def mock_fn():
            if values:
                return values.pop(0)
            return offset_values[-1] if offset_values else 0

        with (
            patch("src.v3xctrl_helper.ntp.shutil.which", return_value=None),
            patch("src.v3xctrl_helper.ntp.get_ntp_offset_ntplib", side_effect=mock_fn),
        ):
            clock = NTPClock(poll_interval=0.05)

        self.addCleanup(clock.stop)
        return clock

    def test_get_time_returns_wall_time_and_offset(self):
        clock = self._make_clock([42])

        # Wait for first poll
        time.sleep(0.1)

        wall_time_us, offset_us = clock.get_time()

        expected_wall = int(time.time() * 1_000_000)
        self.assertAlmostEqual(wall_time_us, expected_wall, delta=50_000)
        self.assertIsInstance(wall_time_us, int)
        self.assertEqual(offset_us, 42)
        self.assertIsInstance(offset_us, int)

    def test_get_time_is_fast(self):
        clock = self._make_clock([0])

        start = time.monotonic()
        for _ in range(1000):
            clock.get_time()
        elapsed = time.monotonic() - start

        # 1000 calls should take well under 100ms
        self.assertLess(elapsed, 0.1)

    def test_starts_with_zero_offset(self):
        clock = self._make_clock([42])

        _, offset = clock.get_time()
        self.assertEqual(offset, 0)

    def test_background_thread_updates_offset(self):
        clock = self._make_clock([100, 200, 300])

        # Wait for at least one background poll
        time.sleep(0.15)

        _, offset = clock.get_time()
        self.assertGreaterEqual(offset, 100)

    def test_keeps_last_offset_on_failure(self):
        call_count = 0

        def failing_after_first():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 500
            raise RuntimeError("network error")

        with (
            patch("src.v3xctrl_helper.ntp.shutil.which", return_value=None),
            patch("src.v3xctrl_helper.ntp.get_ntp_offset_ntplib", side_effect=failing_after_first),
        ):
            clock = NTPClock(poll_interval=0.05)

        self.addCleanup(clock.stop)

        time.sleep(0.15)

        _, offset = clock.get_time()
        self.assertEqual(offset, 500)

    @patch("src.v3xctrl_helper.ntp.shutil.which", return_value="/usr/bin/chronyc")
    @patch("src.v3xctrl_helper.ntp.get_ntp_offset_chrony", return_value=0)
    def test_uses_chrony_when_available(self, mock_chrony, mock_which):
        with self.assertLogs(level=logging.INFO) as cm:
            clock = NTPClock(poll_interval=60)
            clock.stop()

        self.assertTrue(any("chronyc" in msg for msg in cm.output))

    @patch("src.v3xctrl_helper.ntp.shutil.which", return_value=None)
    @patch("src.v3xctrl_helper.ntp.get_ntp_offset_ntplib", return_value=0)
    def test_uses_ntplib_when_chrony_unavailable(self, mock_ntplib, mock_which):
        with self.assertLogs(level=logging.INFO) as cm:
            clock = NTPClock(poll_interval=60)
            clock.stop()

        self.assertTrue(any("ntplib" in msg for msg in cm.output))

    def test_stop_terminates_thread(self):
        clock = self._make_clock([0])

        clock.stop()
        clock._thread.join(timeout=1.0)

        self.assertFalse(clock._thread.is_alive())
