"""Tests for the Telemetry coordinator.

The coordinator owns a TelemetryStore plus one TelemetryCollector per source. These tests
verify wiring (sources registered, rates applied, snapshot exposed) rather than per-source
logic - each source has its own dedicated test module. Sources are constructed lazily on
the collector threads, so the patches stay active for the lifetime of the coordinator.
"""

import sys
import threading
import time
import unittest
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from unittest.mock import MagicMock, patch

_gi_keys = ["gi", "gi.repository", "gi.repository.Gst", "gi.repository.GLib"]
_saved = {key: sys.modules.pop(key, None) for key in _gi_keys}
sys.modules.update({key: MagicMock() for key in _gi_keys})

from src.v3xctrl_control.Telemetry import Telemetry  # noqa: E402
from v3xctrl_telemetry.dataclasses import CellInfo, ModemState, SignalInfo, TelemetryRates  # noqa: E402

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


class Fixture:
    """A coordinator plus the mocks standing in for its sources."""

    def __init__(
        self,
        telemetry: Telemetry,
        sources: dict[str, MagicMock],
        source_classes: dict[str, MagicMock],
    ) -> None:
        self.telemetry = telemetry
        self.sources = sources
        self.source_classes = source_classes


@contextmanager
def _make_telemetry(construction_error: Exception | None = None, **rate_overrides: float) -> Iterator[Fixture]:
    """Build a coordinator with every source class patched.

    The patches outlive __init__ because collectors construct their sources on their own
    threads, at the first tick.
    """
    sources: dict[str, MagicMock] = {}
    source_classes: dict[str, MagicMock] = {}

    with ExitStack() as stack:
        for name, target in SOURCE_PATCHES.items():
            mock_source = MagicMock()
            mock_source.update.return_value = None
            mock_source.get_state.return_value = MagicMock()
            sources[name] = mock_source

            if construction_error is not None:
                source_classes[name] = stack.enter_context(patch(target, side_effect=construction_error))
            else:
                source_classes[name] = stack.enter_context(patch(target, return_value=mock_source))

        rates = replace(
            TelemetryRates(battery=100.0, gst=100.0, videocore=100.0, services=100.0, modem=100.0),
            **rate_overrides,
        )
        # gps_rate_hz drives both module config and collector interval
        telemetry = Telemetry("/dev/modem", gps_rate_hz=100, rates=rates)

        try:
            yield Fixture(telemetry, sources, source_classes)

        finally:
            telemetry.stop()
            for collector in telemetry._collectors:
                if collector.is_alive():
                    collector.join(timeout=1.0)


class TestTelemetryCoordinator(unittest.TestCase):
    def test_get_telemetry_returns_dict(self) -> None:
        with _make_telemetry() as fixture:
            snapshot = fixture.telemetry.get_telemetry()

        self.assertIsInstance(snapshot, dict)
        self.assertIn("sig", snapshot)
        self.assertIn("cell", snapshot)
        self.assertIn("bat", snapshot)
        self.assertIn("loc", snapshot)
        self.assertIn("svc", snapshot)
        self.assertIn("vc", snapshot)
        self.assertIn("gst", snapshot)

    def test_get_telemetry_returns_independent_copy(self) -> None:
        with _make_telemetry() as fixture:
            first = fixture.telemetry.get_telemetry()
            first["sig"]["rsrq"] = 999
            second = fixture.telemetry.get_telemetry()

        self.assertNotEqual(second["sig"]["rsrq"], 999)

    def test_registers_one_collector_per_source(self) -> None:
        with _make_telemetry() as fixture:
            self.assertEqual(len(fixture.telemetry._collectors), 6)

    def test_sources_are_constructed_by_the_collectors_not_the_coordinator(self) -> None:
        with _make_telemetry() as fixture:
            for name, source_class in fixture.source_classes.items():
                self.assertEqual(source_class.call_count, 0, f"{name} was constructed eagerly")

    def test_every_source_keeps_its_collector_when_construction_fails(self) -> None:
        with _make_telemetry(construction_error=RuntimeError("no hardware")) as fixture:
            collectors = fixture.telemetry._collectors
            self.assertEqual(len(collectors), 6)

            fixture.telemetry.start()
            time.sleep(0.05)

            for collector in collectors:
                self.assertTrue(collector.is_alive(), f"{collector.name} died on a construction failure")

    def test_start_starts_all_collectors_then_stop_stops_them(self) -> None:
        with _make_telemetry(modem=200.0) as fixture:
            fixture.telemetry.start()
            time.sleep(0.05)
            for collector in fixture.telemetry._collectors:
                self.assertTrue(collector.is_alive())

            fixture.telemetry.stop()
            for collector in fixture.telemetry._collectors:
                collector.join(timeout=1.0)
                self.assertFalse(collector.is_alive())

    def test_collectors_route_to_store(self) -> None:
        with _make_telemetry(modem=200.0, battery=200.0) as fixture:
            fixture.sources["ModemTelemetry"].get_state.return_value = ModemState(
                signal=SignalInfo(rsrq=-12, rsrp=-90), cell=CellInfo(id="X1", band="3")
            )

            fixture.telemetry.start()
            time.sleep(0.05)

            fixture.sources["ModemTelemetry"].update.assert_called()
            snapshot = fixture.telemetry.get_telemetry()

        self.assertEqual(snapshot["sig"]["rsrq"], -12)
        self.assertEqual(snapshot["sig"]["rsrp"], -90)
        self.assertEqual(snapshot["cell"]["id"], "X1")
        self.assertEqual(snapshot["cell"]["band"], "3")

    def test_collectors_use_distinct_rates(self) -> None:
        # gps interval comes from gps_rate_hz, not a separate update rate
        with _make_telemetry(
            modem=2.0,
            battery=10.0,
            services=0.2,
            videocore=1.0,
            gst=10.0,
        ) as fixture:
            intervals = {collector.name: collector._interval for collector in fixture.telemetry._collectors}

        self.assertAlmostEqual(intervals["telemetry-modem"], 0.5)
        self.assertAlmostEqual(intervals["telemetry-battery"], 0.1)
        self.assertAlmostEqual(intervals["telemetry-gps"], 0.01)  # gps_rate_hz=100 in _make_telemetry default
        self.assertAlmostEqual(intervals["telemetry-services"], 5.0)
        self.assertAlmostEqual(intervals["telemetry-videocore"], 1.0)
        self.assertAlmostEqual(intervals["telemetry-gst"], 0.1)

    def test_gps_collector_uses_gps_rate_hz(self) -> None:
        with _make_telemetry() as fixture:
            intervals = {collector.name: collector._interval for collector in fixture.telemetry._collectors}

        # _make_telemetry defaults gps_rate_hz=100 -> 0.01s
        self.assertAlmostEqual(intervals["telemetry-gps"], 0.01)

    def test_rates_default_to_the_shipped_cadence(self) -> None:
        """Construction is lazy, so the coordinator can be built without any source patched."""
        telemetry = Telemetry("/dev/modem")

        intervals = {collector.name: collector._interval for collector in telemetry._collectors}

        self.assertAlmostEqual(intervals["telemetry-battery"], 0.1)
        self.assertAlmostEqual(intervals["telemetry-gst"], 0.1)
        self.assertAlmostEqual(intervals["telemetry-videocore"], 1.0)
        self.assertAlmostEqual(intervals["telemetry-services"], 5.0)
        self.assertAlmostEqual(intervals["telemetry-modem"], 1.0)
        self.assertAlmostEqual(intervals["telemetry-gps"], 0.2)

    def test_stop_is_safe_when_never_started(self) -> None:
        with _make_telemetry() as fixture:
            fixture.telemetry.stop()  # must not raise

    def test_telemetry_is_not_a_thread(self) -> None:
        """Coordinator delegates threading to collectors and must not subclass Thread itself."""
        with _make_telemetry() as fixture:
            self.assertNotIsInstance(fixture.telemetry, threading.Thread)


if __name__ == "__main__":
    unittest.main()
