import unittest

from v3xctrl_e2e.input_scenario import (
    SCENARIO,
    PhaseWindow,
    Step,
    StepKind,
    assess_axes,
    assess_commands,
    recording_paths,
    run_scenario,
)
from v3xctrl_e2e.log_expectations import LogRecord, LogSource
from v3xctrl_e2e.virtual_gamepad import Axis, Button


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeGamepad:
    def __init__(self) -> None:
        self.events: list[tuple[str, object, object]] = []

    def set_axis(self, axis: Axis, value: float) -> None:
        self.events.append(("axis", axis, value))

    def press(self, button: Button) -> None:
        self.events.append(("press", button, None))

    def release(self, button: Button) -> None:
        self.events.append(("release", button, None))

    def release_all(self) -> None:
        self.events.append(("release_all", None, None))


class TestRunScenario(unittest.TestCase):
    def test_windows_follow_the_clock(self):
        clock = FakeClock()
        gamepad = FakeGamepad()
        steps = (
            Step("forward", StepKind.AXIS, 2.0, axis=Axis.THROTTLE, value=0.5),
            Step("press", StepKind.PRESS, 1.0, button=Button.REC_TOGGLE),
        )

        windows = run_scenario(gamepad, steps, clock, clock.sleep)  # type: ignore[arg-type]

        self.assertEqual(windows[0], PhaseWindow("forward", 100.0, 102.0))
        self.assertEqual(windows[1].phase, "press")
        self.assertEqual(windows[1].start, 102.0)
        self.assertEqual(gamepad.events[0], ("axis", Axis.THROTTLE, 0.5))
        self.assertEqual(gamepad.events[1], ("press", Button.REC_TOGGLE, None))
        self.assertEqual(gamepad.events[2], ("release", Button.REC_TOGGLE, None))
        self.assertEqual(gamepad.events[-1], ("release_all", None, None))

    def test_scenario_is_net_zero_on_trim(self):
        stop_step = next(step for step in SCENARIO if step.phase == "recording-stop")
        self.assertGreaterEqual(stop_step.seconds, 7.0)
        increases = sum(1 for step in SCENARIO if step.button == Button.TRIM_INCREASE)
        decreases = sum(1 for step in SCENARIO if step.button == Button.TRIM_DECREASE)

        self.assertEqual(increases, decreases)


def control(at: float, throttle: float, steering: float) -> LogRecord:
    return LogRecord(LogSource.CONTROL, f"12:00 - DEBUG - Throttle: {throttle}; Steering: {steering}", at)


WINDOWS = [
    PhaseWindow("throttle-forward", 0.0, 2.0),
    PhaseWindow("throttle-release", 2.0, 3.5),
    PhaseWindow("steering-left", 3.5, 5.0),
    PhaseWindow("steering-right", 5.0, 6.5),
    PhaseWindow("steering-release", 6.5, 8.0),
]


def moving_rig() -> list[LogRecord]:
    return [
        control(0.5, 1700, 1500),
        control(1.5, 1700, 1500),
        control(2.5, 1500, 1500),
        control(3.0, 1500, 1500),
        control(4.0, 1500, 1300),
        control(4.5, 1500, 1300),
        control(5.5, 1500, 1700),
        control(6.0, 1500, 1700),
        control(7.0, 1500, 1500),
        control(7.5, 1500, 1500),
    ]


class TestAssessAxes(unittest.TestCase):
    def test_moving_and_settling_values_pass(self):
        self.assertEqual(assess_axes(moving_rig(), WINDOWS), [])

    def test_frozen_values_fail(self):
        records = [control(at, 1500, 1500) for at in (0.5, 1.5, 2.5, 3.0, 4.0, 4.5, 5.5, 6.0, 7.0, 7.5)]

        failures = assess_axes(records, WINDOWS)

        self.assertEqual(len(failures), 2)
        self.assertIn("throttle pulse width moved 0us", failures[0])
        self.assertIn("steering pulse width moved 0us", failures[1])

    def test_no_control_lines_fail(self):
        failures = assess_axes([], WINDOWS)

        self.assertEqual(len(failures), 2)

    def test_steering_must_move_in_opposite_directions(self):
        records = moving_rig()
        records[6] = control(5.5, 1500, 1300)
        records[7] = control(6.0, 1500, 1300)

        failures = assess_axes(records, WINDOWS)

        self.assertEqual(
            failures,
            [
                "input: steering left and right moved the pulse width in the same direction, "
                "1300us and 1300us from idle 1500us"
            ],
        )

    def test_a_window_shifted_into_the_previous_phase_still_passes(self):
        """A few hundred milliseconds of clock skew leaves the tail of the left
        phase in the right window; the settled value decides, not the extreme."""
        records = moving_rig()
        records.insert(6, control(5.2, 1500, 1249))
        records.insert(7, control(5.4, 1500, 1249))

        self.assertEqual(assess_axes(records, WINDOWS), [])

    def test_not_settling_fails(self):
        records = moving_rig()
        records[3] = control(3.0, 1700, 1500)
        records[2] = control(2.5, 1700, 1500)

        failures = assess_axes(records, WINDOWS)

        self.assertEqual(len(failures), 1)
        self.assertIn("throttle pulse width moved 0us", failures[0])


def viewer(text: str) -> LogRecord:
    return LogRecord(LogSource.VIEWER, text, 0.0)


def journal(source: LogSource, text: str) -> LogRecord:
    return LogRecord(source, text, 0.0)


def complete_command_records() -> list[LogRecord]:
    records = [viewer("Sending command: trim {'action': 'increase'}")] * 2
    records += [viewer("Sending command: trim {'action': 'decrease'}")] * 2
    records += [
        viewer("Sending command: recording {'action': 'start'}"),
        viewer("Sending command: recording {'action': 'stop'}"),
    ]
    records += [viewer("Received command ack: True")] * 6
    records += [journal(LogSource.CONTROL, "Received command: <Command c=trim>")] * 4
    records += [journal(LogSource.CONTROL, "Received command: <Command c=recording>")] * 2
    records += [
        journal(LogSource.VIDEO, "Recording started: /data/recordings/stream-1.ts"),
        journal(LogSource.VIDEO, "Recording stopped: /data/recordings/stream-1.ts"),
    ]
    return records


class TestAssessCommands(unittest.TestCase):
    def test_complete_records_pass(self):
        self.assertEqual(assess_commands(complete_command_records()), [])

    def test_missing_acknowledgement_fails(self):
        records = [record for record in complete_command_records() if "ack" not in record.text]

        failures = assess_commands(records)

        self.assertEqual(failures, ["input: command acknowledged: expected at least 6, saw 0"])


class TestRecordingPaths(unittest.TestCase):
    def test_forced_teardown_is_reported(self):
        records = [
            *complete_command_records(),
            journal(LogSource.VIDEO, "Recording stop timed out, forcing teardown"),
            journal(LogSource.VIDEO, "Recording stopped (forced): /data/recordings/stream-2.ts"),
        ]

        failures = assess_commands(records)

        self.assertTrue(any("forced the recording teardown" in failure for failure in failures))
        self.assertIn("/data/recordings/stream-2.ts", recording_paths(records))

    def test_extracts_stopped_recordings(self):
        records = [*complete_command_records(), journal(LogSource.VIDEO, "Recording stopped: unknown")]

        self.assertEqual(recording_paths(records), ["/data/recordings/stream-1.ts"])
