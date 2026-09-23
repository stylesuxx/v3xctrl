"""Tests for TrackLoggingGps."""

import unittest
from unittest.mock import MagicMock

from v3xctrl_telemetry.dataclasses import GpsFix, LocationInfo
from v3xctrl_telemetry.GpsTelemetry import GpsTelemetry
from v3xctrl_telemetry.GpsTrackLogger import GpsTrackLogger
from v3xctrl_telemetry.TelemetrySource import TelemetrySource
from v3xctrl_telemetry.TrackLoggingGps import TrackLoggingGps


def _make(updated=True, fix=None):
    gps = MagicMock(spec=GpsTelemetry)
    gps.update.return_value = updated
    gps.get_fix.return_value = fix if fix is not None else GpsFix(lat=52.52, lng=13.405)
    track_logger = MagicMock(spec=GpsTrackLogger)
    return TrackLoggingGps(gps, track_logger), gps, track_logger


class TestDelegation(unittest.TestCase):
    def test_satisfies_the_telemetry_source_protocol(self):
        wrapper, _, _ = _make()

        self.assertIsInstance(wrapper, TelemetrySource)

    def test_update_returns_what_the_gps_returned(self):
        for updated in (True, False):
            wrapper, _, _ = _make(updated=updated)

            self.assertIs(wrapper.update(), updated)

    def test_get_state_comes_from_the_gps(self):
        wrapper, gps, _ = _make()
        state = LocationInfo(lat=48.1, lng=11.5)
        gps.get_state.return_value = state

        self.assertIs(wrapper.get_state(), state)


class TestForwarding(unittest.TestCase):
    def test_new_fix_is_forwarded(self):
        fix = GpsFix(lat=1.0, lng=2.0)
        wrapper, _, track_logger = _make(fix=fix)

        wrapper.update()

        track_logger.add_fix.assert_called_once_with(fix)

    def test_stale_fix_is_not_forwarded(self):
        """A poll that read nothing returns the last fix again; counting it twice would skew
        the hysteresis and keep a dead GPS writing heartbeat points."""
        wrapper, _, track_logger = _make(updated=False)

        wrapper.update()

        track_logger.add_fix.assert_not_called()

    def test_missing_fix_is_not_forwarded(self):
        wrapper, gps, track_logger = _make()
        gps.get_fix.return_value = None

        wrapper.update()

        track_logger.add_fix.assert_not_called()


class TestWriteFailures(unittest.TestCase):
    def test_write_failure_does_not_reach_the_collector(self):
        wrapper, _, track_logger = _make()
        track_logger.add_fix.side_effect = OSError("No space left on device")

        with self.assertLogs("v3xctrl_telemetry.TrackLoggingGps", level="WARNING"):
            self.assertTrue(wrapper.update())

    def test_repeated_failures_warn_once(self):
        wrapper, _, track_logger = _make()
        track_logger.add_fix.side_effect = OSError("No space left on device")

        with self.assertLogs("v3xctrl_telemetry.TrackLoggingGps", level="WARNING") as captured:
            for _ in range(5):
                wrapper.update()

        self.assertEqual(len(captured.records), 1)

    def test_recovery_is_logged(self):
        wrapper, _, track_logger = _make()
        track_logger.add_fix.side_effect = OSError("No space left on device")
        with self.assertLogs("v3xctrl_telemetry.TrackLoggingGps", level="WARNING"):
            wrapper.update()

        track_logger.add_fix.side_effect = None
        with self.assertLogs("v3xctrl_telemetry.TrackLoggingGps", level="INFO") as captured:
            wrapper.update()

        self.assertIn("recovered", captured.output[0])

    def test_non_io_errors_are_not_swallowed(self):
        """Only disk trouble is contained; a bug in the logger should still surface."""
        wrapper, _, track_logger = _make()
        track_logger.add_fix.side_effect = ValueError("bug")

        with self.assertRaises(ValueError):
            wrapper.update()
