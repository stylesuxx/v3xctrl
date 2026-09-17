import time
import unittest

from v3xctrl_control.message import Latency, Telemetry
from v3xctrl_helper import SlidingWindowAverage
from v3xctrl_ui.core.StatusLevel import StatusLevel
from v3xctrl_ui.core.TelemetryContext import TelemetryContext
from v3xctrl_ui.core.TelemetrySink import TelemetrySink


def latency_message(seconds_ago: float) -> Latency:
    message = Latency()
    message.timestamp = time.time() - seconds_ago

    return message


def telemetry_message() -> Telemetry:
    return Telemetry(
        {
            "sig": {"rsrq": -9, "rsrp": -95},
            "cell": {"band": 3, "id": 0x0000F002},
            "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False},
        }
    )


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestTelemetrySink(unittest.TestCase):
    """Ingestion is exercised without a display, which is the point of the sink."""

    def setUp(self):
        self.telemetry_context = TelemetryContext()
        self.sink = TelemetrySink(self.telemetry_context)

    def test_initial_latency_reading(self):
        reading = self.sink.latency

        self.assertIsNone(reading.milliseconds)
        self.assertEqual(reading.level, StatusLevel.NEUTRAL)
        self.assertTrue(reading.is_measurable)

    def test_telemetry_lands_in_the_context(self):
        telemetry = Telemetry(
            {
                "sig": {"rsrq": -9, "rsrp": -95},
                "cell": {"band": 3, "id": 0x0000F002},
                "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False},
            }
        )

        self.sink.handle_message(telemetry)

        signal = self.telemetry_context.get_signal()
        battery = self.telemetry_context.get_battery()
        self.assertEqual(signal.quality["rsrq"], -9)
        self.assertEqual(signal.band, "BAND 3")
        self.assertEqual(signal.cell, "240:2")
        self.assertEqual(battery.percent, "75%")

    def test_latency_sets_a_reading(self):
        self.sink.handle_message(latency_message(0.05))

        reading = self.sink.latency
        self.assertIsInstance(reading.milliseconds, int)
        self.assertTrue(reading.is_measurable)

    def test_latency_levels_by_range(self):
        for seconds_ago, expected in [(0.05, StatusLevel.GOOD), (0.1, StatusLevel.WARNING), (0.2, StatusLevel.BAD)]:
            self.sink._latency_samples.clear()
            self.sink.handle_message(latency_message(seconds_ago))

            self.assertEqual(self.sink.latency.level, expected)

    def test_latency_is_not_measurable_while_spectating(self):
        self.sink.set_spectator_mode(True)

        self.sink.handle_message(latency_message(0.05))

        reading = self.sink.latency
        self.assertFalse(reading.is_measurable)
        self.assertIsNone(reading.milliseconds)
        self.assertEqual(reading.level, StatusLevel.NEUTRAL)

    def test_latency_resumes_after_spectating(self):
        self.sink.set_spectator_mode(True)
        self.sink.set_spectator_mode(False)

        self.sink.handle_message(latency_message(0.05))

        reading = self.sink.latency
        self.assertEqual(reading.level, StatusLevel.GOOD)
        self.assertIsInstance(reading.milliseconds, int)

    def test_latency_averages_multiple_samples(self):
        # ~40ms and ~60ms round trip, so ~20ms and ~30ms one way
        self.sink.handle_message(latency_message(0.04))
        self.sink.handle_message(latency_message(0.06))

        reading = self.sink.latency
        self.assertEqual(reading.level, StatusLevel.GOOD)
        self.assertGreater(reading.milliseconds, 15)
        self.assertLess(reading.milliseconds, 35)

    def test_latency_evicts_old_samples(self):
        self.sink._latency_samples = SlidingWindowAverage(window_seconds=0.5)
        self.sink._latency_samples._samples.append((time.monotonic() - 1.0, 200.0))

        self.sink.handle_message(latency_message(0.05))

        self.assertEqual(len(self.sink._latency_samples), 1)
        self.assertEqual(self.sink.latency.level, StatusLevel.GOOD)

    def test_reset_clears_context_and_latency(self):
        self.sink.handle_message(
            Telemetry(
                {
                    "sig": {"rsrq": -9, "rsrp": -95},
                    "cell": {"band": 3, "id": 0x0000F002},
                    "bat": {"vol": 3800, "avg": 3750, "pct": 75, "wrn": False},
                }
            )
        )
        self.sink.handle_message(latency_message(0.05))

        self.sink.reset()

        self.assertEqual(self.telemetry_context.get_signal().quality, {"rsrq": -1, "rsrp": -1})
        self.assertEqual(self.telemetry_context.get_battery().percent, "0%")
        self.assertEqual(len(self.sink._latency_samples), 0)
        self.assertIsNone(self.sink.latency.milliseconds)
        self.assertEqual(self.sink.latency.level, StatusLevel.NEUTRAL)

    def test_first_telemetry_is_logged_once_per_connection(self):
        with self.assertLogs("v3xctrl_ui.core.TelemetrySink", level="INFO") as logs:
            self.sink.handle_message(telemetry_message())
            self.sink.handle_message(telemetry_message())

        self.assertEqual(logs.output.count("INFO:v3xctrl_ui.core.TelemetrySink:First telemetry message received"), 1)

    def test_first_telemetry_is_logged_again_after_reset(self):
        self.sink.handle_message(telemetry_message())
        self.sink.reset()

        with self.assertLogs("v3xctrl_ui.core.TelemetrySink", level="INFO") as logs:
            self.sink.handle_message(telemetry_message())

        self.assertIn("INFO:v3xctrl_ui.core.TelemetrySink:First telemetry message received", logs.output)

    def test_telemetry_count_is_reported_once_per_interval(self):
        clock = FakeClock()
        sink = TelemetrySink(self.telemetry_context, report_interval_seconds=10.0, clock=clock)

        with self.assertLogs("v3xctrl_ui.core.TelemetrySink", level="INFO") as logs:
            for _ in range(9):
                sink.handle_message(telemetry_message())
                clock.advance(1.0)

            sink.handle_message(telemetry_message())
            clock.advance(1.0)
            sink.handle_message(telemetry_message())

        count_lines = [line for line in logs.output if "messages in last" in line]
        self.assertEqual(count_lines, ["INFO:v3xctrl_ui.core.TelemetrySink:Telemetry: 11 messages in last 10s"])

    def test_telemetry_count_window_restarts_after_report(self):
        clock = FakeClock()
        sink = TelemetrySink(self.telemetry_context, report_interval_seconds=10.0, clock=clock)

        # The first message anchors the window, so the report fires on the
        # message that lands 10 s later and every 10 s after that
        with self.assertLogs("v3xctrl_ui.core.TelemetrySink", level="INFO") as logs:
            for _ in range(21):
                sink.handle_message(telemetry_message())
                clock.advance(1.0)

        count_lines = [line for line in logs.output if "messages in last" in line]
        self.assertEqual(
            count_lines,
            [
                "INFO:v3xctrl_ui.core.TelemetrySink:Telemetry: 11 messages in last 10s",
                "INFO:v3xctrl_ui.core.TelemetrySink:Telemetry: 10 messages in last 10s",
            ],
        )


if __name__ == "__main__":
    unittest.main()
