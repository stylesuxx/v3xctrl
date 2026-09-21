import unittest

from v3xctrl_e2e.log_expectations import (
    Forbidden,
    LogRecord,
    LogSource,
    ReceiverStats,
    Required,
    TelemetryCount,
    check_telemetry_rate,
    check_video_flow,
    control_values,
    evaluate,
    lowest_fps,
    parse_control_values,
    parse_receiver_stats,
    parse_telemetry_count,
    receiver_stats,
    slice_after,
    slice_between,
    telemetry_counts,
)

STATS_LINE = (
    "2026-09-16 14:41:56,475 - INFO - ReceiverGst: frames=121, dropped_empty=0, dropped_old=0, dropped_burst=61, "
    "drop_rate=50.4%, avg_decoded_fps=12, avg_rendered_fps=6, avg_jitter=103.1ms, max_jitter=2097.4ms"
)


def viewer(text: str, at: float = 0.0) -> LogRecord:
    return LogRecord(LogSource.VIEWER, text, at)


def control(text: str, at: float = 0.0) -> LogRecord:
    return LogRecord(LogSource.CONTROL, text, at)


class TestParsing(unittest.TestCase):
    def test_receiver_stats_line(self):
        stats = parse_receiver_stats(STATS_LINE)

        self.assertEqual(
            stats,
            ReceiverStats(
                frames=121,
                dropped_empty=0,
                dropped_old=0,
                dropped_burst=61,
                drop_rate=50.4,
                avg_decoded_fps=12,
                avg_rendered_fps=6,
                avg_jitter=103.1,
                max_jitter=2097.4,
            ),
        )

    def test_receiver_stats_ignores_other_lines(self):
        self.assertIsNone(parse_receiver_stats("2026-09-16 14:41:46,403 - INFO - Pipeline is now PLAYING"))

    def test_telemetry_count_line(self):
        count = parse_telemetry_count("2026-09-16 14:42:37,520 - INFO - Telemetry: 10 messages in last 10s")

        assert count is not None
        self.assertEqual(count, TelemetryCount(messages=10, seconds=10))
        self.assertAlmostEqual(count.rate_hz, 1.0)

    def test_control_values_line(self):
        values = parse_control_values("2026-09-16 14:42:37,520 - DEBUG - Throttle: 1500; Steering: 1480.5")

        assert values is not None
        self.assertEqual(values.throttle, 1500.0)
        self.assertEqual(values.steering, 1480.5)

    def test_control_values_channel_line(self):
        values = parse_control_values("2026-09-22 20:31:05,120 - DEBUG - Channel A: 1620; Channel B: 1500")

        assert values is not None
        self.assertEqual(values.throttle, 1620.0)
        self.assertEqual(values.steering, 1500.0)

    def test_collectors_filter_by_source(self):
        records = [
            viewer(STATS_LINE),
            control(STATS_LINE),
            viewer("Telemetry: 9 messages in last 10s"),
            control("Throttle: 1500; Steering: 1500"),
            viewer("Throttle: 1; Steering: 2"),
        ]

        self.assertEqual(len(receiver_stats(records)), 1)
        self.assertEqual(telemetry_counts(records), [TelemetryCount(9, 10)])
        self.assertEqual([value.throttle for value in control_values(records)], [1500.0])

    def test_count_lines_straddling_the_window_start_are_dropped(self):
        records = [
            viewer("Telemetry: 2 messages in last 11s", at=105.0),
            viewer("Telemetry: 10 messages in last 10s", at=115.0),
        ]

        self.assertEqual(telemetry_counts(records, window_start=100.0), [TelemetryCount(10, 10)])


class TestEvaluate(unittest.TestCase):
    def test_required_counts_matches(self):
        records = [viewer("TcpTunnel handshake complete (12 bytes)"), viewer("TcpTunnel handshake complete (12 bytes)")]
        required = [Required("handshakes", LogSource.VIEWER, r"TcpTunnel handshake complete", minimum_count=2)]

        self.assertEqual(evaluate(records, required, []), [])

    def test_required_reports_shortfall(self):
        required = [Required("handshakes", LogSource.VIEWER, r"TcpTunnel handshake complete", minimum_count=2)]

        failures = evaluate([viewer("TcpTunnel handshake complete (12 bytes)")], required, [])

        self.assertEqual(len(failures), 1)
        self.assertIn("expected at least 2", failures[0])
        self.assertIn("saw 1", failures[0])

    def test_required_is_source_specific(self):
        required = [Required("connected", LogSource.VIEWER, r"Control channel connected")]

        failures = evaluate([control("Control channel connected")], required, [])

        self.assertEqual(len(failures), 1)

    def test_forbidden_reports_the_offending_line(self):
        forbidden = [Forbidden("errors", LogSource.CONTROL, r" - ERROR - ")]

        failures = evaluate([control("12:00:00 - ERROR - No message received for 0.15s")], [], forbidden)

        self.assertEqual(failures, ["errors: v3xctrl-control: 12:00:00 - ERROR - No message received for 0.15s"])

    def test_repeated_forbidden_hits_collapse_into_one_line(self):
        forbidden = [Forbidden("errors", LogSource.CONTROL, r" - ERROR - ")]
        records = [
            control("2026-09-23 00:22:05,443 - ERROR - No message received for 0.15s"),
            control("2026-09-23 00:22:06,871 - ERROR - No message received for 0.15s"),
            control("2026-09-23 00:26:19,726 - ERROR - No message received for 0.15s"),
        ]

        failures = evaluate(records, [], forbidden)

        self.assertEqual(
            failures,
            [
                "errors: 3 times from 00:22:05 to 00:26:19, first: v3xctrl-control: "
                "2026-09-23 00:22:05,443 - ERROR - No message received for 0.15s"
            ],
        )

    def test_repeated_hits_without_timestamps_report_the_count(self):
        forbidden = [Forbidden("tracebacks", LogSource.CONTROL, r"Traceback")]
        records = [control("Traceback (most recent call last):"), control("Traceback (most recent call last):")]

        failures = evaluate(records, [], forbidden)

        self.assertEqual(failures, ["tracebacks: 2 times, first: v3xctrl-control: Traceback (most recent call last):"])

    def test_forbidden_allowlist_exempts_known_lines(self):
        forbidden = [
            Forbidden("errors", LogSource.CONTROL, r" - (ERROR|WARNING) - ", allowed=(r"Failed to initialize modem",))
        ]
        records = [
            control("12:00:00 - WARNING - Failed to initialize modem: no such file"),
            control("12:00:01 - ERROR - Unexpected transmit error"),
        ]

        failures = evaluate(records, [], forbidden)

        self.assertEqual(len(failures), 1)
        self.assertIn("Unexpected transmit error", failures[0])


class TestSlicing(unittest.TestCase):
    def test_slices_by_capture_time(self):
        records = [viewer("a", 1.0), viewer("b", 2.0), viewer("c", 3.0)]

        self.assertEqual([record.text for record in slice_after(records, 2.0)], ["b", "c"])
        self.assertEqual([record.text for record in slice_between(records, 1.5, 2.5)], ["b"])


def stats(fps: int, drop_rate: float) -> ReceiverStats:
    return ReceiverStats(100, 0, 0, 0, drop_rate, fps, fps, 1.0, 2.0)


class TestVideoFlow(unittest.TestCase):
    def test_needs_two_lines(self):
        self.assertEqual(len(check_video_flow([stats(30, 0.0)], 25, 2.0)), 1)

    def test_first_line_is_a_partial_interval_and_ignored(self):
        self.assertEqual(check_video_flow([stats(3, 0.0), stats(29, 0.5)], 25, 2.0), [])

    def test_soak_tolerates_one_slow_window(self):
        windows = [stats(3, 0.0), stats(29, 0.0), stats(21, 0.0), stats(30, 0.0)]

        self.assertEqual(check_video_flow(windows, 25, 2.0, consecutive_low_windows=2), [])
        self.assertEqual(len(check_video_flow(windows, 25, 2.0)), 1)

    def test_soak_fails_on_two_slow_windows_in_a_row(self):
        windows = [stats(3, 0.0), stats(21, 0.0), stats(22, 0.0), stats(30, 0.0)]

        failures = check_video_flow(windows, 25, 2.0, consecutive_low_windows=2)

        self.assertEqual(len(failures), 1)
        self.assertIn("2 windows in a row", failures[0])

    def test_lowest_fps_skips_the_partial_first_window(self):
        self.assertEqual(lowest_fps([stats(3, 0.0), stats(29, 0.0), stats(21, 0.0)]), 21)
        self.assertIsNone(lowest_fps([stats(3, 0.0)]))

    def test_low_fps_and_high_drop_rate_fail(self):
        failures = check_video_flow([stats(30, 0.0), stats(12, 50.4)], 25, 2.0)

        self.assertEqual(len(failures), 2)
        self.assertIn("avg_decoded_fps 12 below 25", failures[0])
        self.assertIn("drop_rate 50.4% above 2.0%", failures[1])


class TestTelemetryRate(unittest.TestCase):
    def test_no_count_lines_fails(self):
        self.assertEqual(len(check_telemetry_rate([], 1.0, 0.2)), 1)

    def test_rate_within_tolerance_passes(self):
        self.assertEqual(check_telemetry_rate([TelemetryCount(9, 10), TelemetryCount(11, 11)], 1.0, 0.2), [])

    def test_rate_below_tolerance_fails(self):
        failures = check_telemetry_rate([TelemetryCount(3, 15)], 1.0, 0.2)

        self.assertEqual(len(failures), 1)
        self.assertIn("0.20 Hz", failures[0])
