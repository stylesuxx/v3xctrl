"""Tests for the Telemetry coordinator.

The coordinator owns a TelemetryStore plus one TelemetryCollector per source. These tests
drive it through its own interface - start, stop, join, get_telemetry - with every source
class patched. Sources are constructed lazily on the collector threads, so the patches stay
active for the lifetime of the coordinator.
"""

import sys
import time
import unittest
from collections.abc import Callable, Iterator
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


def _wait_until(predicate: Callable[[], bool], timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)

    return predicate()


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
            telemetry.join(timeout=1.0)


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

    def test_sources_are_constructed_by_the_collectors_not_the_coordinator(self) -> None:
        with _make_telemetry() as fixture:
            for name, source_class in fixture.source_classes.items():
                self.assertEqual(source_class.call_count, 0, f"{name} was constructed eagerly")

    def test_every_source_is_polled_after_start(self) -> None:
        with _make_telemetry() as fixture:
            fixture.telemetry.start()

            polled = _wait_until(lambda: all(source.update.called for source in fixture.sources.values()))

            unpolled = [name for name, source in fixture.sources.items() if not source.update.called]
            self.assertTrue(polled, f"never polled: {unpolled}")

    def test_every_source_is_retried_when_construction_fails(self) -> None:
        with _make_telemetry(construction_error=RuntimeError("no hardware")) as fixture:
            fixture.telemetry.start()

            attempted = _wait_until(
                lambda: all(source_class.call_count >= 1 for source_class in fixture.source_classes.values())
            )

            self.assertTrue(attempted, "a failing source was dropped instead of retried")
            self.assertIsInstance(fixture.telemetry.get_telemetry(), dict)

    def test_stop_halts_polling(self) -> None:
        with _make_telemetry() as fixture:
            fixture.telemetry.start()
            self.assertTrue(_wait_until(lambda: fixture.sources["ModemTelemetry"].update.called))

            fixture.telemetry.stop()
            fixture.telemetry.join(timeout=1.0)
            counts = {name: source.update.call_count for name, source in fixture.sources.items()}

            time.sleep(0.05)

            for name, source in fixture.sources.items():
                self.assertEqual(source.update.call_count, counts[name], f"{name} kept polling after stop")

    def test_collectors_route_to_store(self) -> None:
        with _make_telemetry() as fixture:
            fixture.sources["ModemTelemetry"].get_state.return_value = ModemState(
                signal=SignalInfo(rsrq=-12, rsrp=-90), cell=CellInfo(id="X1", band="3")
            )

            fixture.telemetry.start()
            self.assertTrue(_wait_until(lambda: fixture.telemetry.get_telemetry()["cell"]["id"] == "X1"))

            snapshot = fixture.telemetry.get_telemetry()

        self.assertEqual(snapshot["sig"]["rsrq"], -12)
        self.assertEqual(snapshot["sig"]["rsrp"], -90)
        self.assertEqual(snapshot["cell"]["band"], "3")

    def test_stop_is_safe_when_never_started(self) -> None:
        with _make_telemetry() as fixture:
            fixture.telemetry.stop()  # must not raise

    def test_join_is_safe_when_never_started(self) -> None:
        with _make_telemetry() as fixture:
            fixture.telemetry.join(timeout=0.1)  # must not raise

    def test_join_returns_within_its_timeout(self) -> None:
        """The timeout bounds the total wait, not each collector."""
        with _make_telemetry() as fixture:
            fixture.telemetry.start()
            self.assertTrue(_wait_until(lambda: fixture.sources["ModemTelemetry"].update.called))

            fixture.telemetry.stop()
            started_at = time.monotonic()
            fixture.telemetry.join(timeout=1.0)
            elapsed = time.monotonic() - started_at

        self.assertLess(elapsed, 1.5, f"join overran its timeout (elapsed={elapsed:.3f}s)")


class TestRateWiringInternals(unittest.TestCase):
    """Tests at an internal seam: they read collector intervals directly.

    Nothing in the coordinator's interface exposes a poll rate, so these describe the
    implementation rather than the contract, and go with it if the wiring moves.
    """

    def test_each_source_gets_its_configured_rate(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
