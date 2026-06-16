"""Tests for the Telemetry coordinator.

The coordinator owns a TelemetryStore plus one TelemetryCollector per source.
These tests verify wiring (sources registered, snapshot exposed) rather than
per-source logic - each source has its own dedicated test module.
"""

import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

_gi_keys = ["gi", "gi.repository", "gi.repository.Gst", "gi.repository.GLib"]
_saved = {key: sys.modules.pop(key, None) for key in _gi_keys}
sys.modules.update({key: MagicMock() for key in _gi_keys})

from src.v3xctrl_control.Telemetry import Telemetry  # noqa: E402
from v3xctrl_telemetry.dataclasses import ModemState  # noqa: E402

for _key in _gi_keys:
    if _saved[_key] is not None:
        sys.modules[_key] = _saved[_key]
    else:
        sys.modules.pop(_key, None)


SOURCE_PATCHES = {
    "ModemTelemetry": "src.v3xctrl_control.Telemetry.ModemTelemetry",
    "BatteryTelemetry": "src.v3xctrl_control.Telemetry.BatteryTelemetry",
    "UBXGpsTelemetry": "src.v3xctrl_control.Telemetry.UBXGpsTelemetry",
    "ServiceTelemetry": "src.v3xctrl_control.Telemetry.ServiceTelemetry",
    "VideoCoreTelemetry": "src.v3xctrl_control.Telemetry.VideoCoreTelemetry",
    "GstTelemetry": "src.v3xctrl_control.Telemetry.GstTelemetry",
}


def _make_telemetry(**overrides: float) -> tuple[Telemetry, dict[str, MagicMock]]:
    """Construct a Telemetry coordinator with every source replaced by a MagicMock.

    Returns (telemetry, mocks) so individual tests can introspect the mocks.
    """
    mocks: dict[str, MagicMock] = {}
    patchers = []
    for name, target in SOURCE_PATCHES.items():
        mock_source = MagicMock()
        mock_source.update.return_value = None
        mock_source.get_state.return_value = MagicMock()
        mocks[name] = mock_source

        patcher = patch(target, return_value=mock_source)
        patcher.start()
        patchers.append(patcher)

    try:
        defaults: dict[str, float] = {
            "modem_update_rate": 100.0,
            "battery_update_rate": 100.0,
            "services_update_rate": 100.0,
            "videocore_update_rate": 100.0,
            "gst_update_rate": 100.0,
        }
        defaults.update(overrides)
        # gps_rate_hz drives both module config and collector interval
        telemetry = Telemetry("/dev/modem", gps_rate_hz=100, **defaults)
    finally:
        for p in patchers:
            p.stop()
    return telemetry, mocks


class TestTelemetryCoordinator(unittest.TestCase):
    def test_get_telemetry_returns_dict(self) -> None:
        telemetry, _ = _make_telemetry()
        snapshot = telemetry.get_telemetry()
        self.assertIsInstance(snapshot, dict)
        self.assertIn("sig", snapshot)
        self.assertIn("cell", snapshot)
        self.assertIn("bat", snapshot)
        self.assertIn("loc", snapshot)
        self.assertIn("svc", snapshot)
        self.assertIn("vc", snapshot)
        self.assertIn("gst", snapshot)

    def test_get_telemetry_returns_independent_copy(self) -> None:
        telemetry, _ = _make_telemetry()
        first = telemetry.get_telemetry()
        first["sig"]["rsrq"] = 999
        second = telemetry.get_telemetry()
        self.assertNotEqual(second["sig"]["rsrq"], 999)

    def test_registers_one_collector_per_source(self) -> None:
        telemetry, _ = _make_telemetry()
        # All six sources patched to construct successfully -> 6 collectors
        self.assertEqual(len(telemetry._collectors), 6)

    def test_failed_source_init_skips_collector(self) -> None:
        with (
            patch(SOURCE_PATCHES["ModemTelemetry"], side_effect=RuntimeError("boom")),
            patch(SOURCE_PATCHES["BatteryTelemetry"], return_value=MagicMock()),
            patch(SOURCE_PATCHES["UBXGpsTelemetry"], return_value=MagicMock()),
            patch(SOURCE_PATCHES["ServiceTelemetry"], return_value=MagicMock()),
            patch(SOURCE_PATCHES["VideoCoreTelemetry"], return_value=MagicMock()),
            patch(SOURCE_PATCHES["GstTelemetry"], return_value=MagicMock()),
        ):
            telemetry = Telemetry("/dev/modem")

        # 5 collectors instead of 6 (modem failed)
        self.assertEqual(len(telemetry._collectors), 5)
        self.assertFalse(any(c.name == "telemetry-modem" for c in telemetry._collectors))

    def test_start_starts_all_collectors_then_stop_stops_them(self) -> None:
        telemetry, _ = _make_telemetry(modem_update_rate=200.0)
        try:
            telemetry.start()
            time.sleep(0.05)
            for c in telemetry._collectors:
                self.assertTrue(c.is_alive())
        finally:
            telemetry.stop()
            for c in telemetry._collectors:
                c.join(timeout=1.0)
                self.assertFalse(c.is_alive())

    def test_collectors_route_to_store(self) -> None:
        telemetry, mocks = _make_telemetry(modem_update_rate=200.0, battery_update_rate=200.0)
        mocks["ModemTelemetry"].get_state.return_value = ModemState(rsrq=-12, rsrp=-90, cell_id="X1", band="3")

        try:
            telemetry.start()
            time.sleep(0.05)
            mocks["ModemTelemetry"].update.assert_called()
            snapshot = telemetry.get_telemetry()
            self.assertEqual(snapshot["sig"]["rsrq"], -12)
            self.assertEqual(snapshot["sig"]["rsrp"], -90)
            self.assertEqual(snapshot["cell"]["id"], "X1")
            self.assertEqual(snapshot["cell"]["band"], "3")
        finally:
            telemetry.stop()
            for c in telemetry._collectors:
                c.join(timeout=1.0)

    def test_collectors_use_distinct_rates(self) -> None:
        # gps interval comes from gps_rate_hz, not a separate update rate
        telemetry, _ = _make_telemetry(
            modem_update_rate=2.0,
            battery_update_rate=10.0,
            services_update_rate=0.2,
            videocore_update_rate=1.0,
            gst_update_rate=10.0,
        )
        intervals = {c.name: c._interval for c in telemetry._collectors}
        self.assertAlmostEqual(intervals["telemetry-modem"], 0.5)
        self.assertAlmostEqual(intervals["telemetry-battery"], 0.1)
        self.assertAlmostEqual(intervals["telemetry-gps"], 0.01)  # gps_rate_hz=100 in _make_telemetry default
        self.assertAlmostEqual(intervals["telemetry-services"], 5.0)
        self.assertAlmostEqual(intervals["telemetry-videocore"], 1.0)
        self.assertAlmostEqual(intervals["telemetry-gst"], 0.1)

    def test_gps_collector_uses_gps_rate_hz(self) -> None:
        # gps_rate_hz drives the collector poll interval, not a separate update rate
        telemetry, _ = _make_telemetry()
        intervals = {c.name: c._interval for c in telemetry._collectors}
        # _make_telemetry defaults gps_rate_hz=100 -> 0.01s
        self.assertAlmostEqual(intervals["telemetry-gps"], 0.01)

    def test_stop_is_safe_when_never_started(self) -> None:
        telemetry, _ = _make_telemetry()
        telemetry.stop()  # must not raise

    def test_telemetry_is_not_a_thread(self) -> None:
        """Coordinator delegates threading to collectors and must not subclass Thread itself."""
        telemetry, _ = _make_telemetry()
        self.assertNotIsInstance(telemetry, threading.Thread)


if __name__ == "__main__":
    unittest.main()
