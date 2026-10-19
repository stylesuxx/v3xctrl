"""The scripted gamepad session and the log assertions that go with it.

Control values are only compared relative to each other: the pulse widths
the streamer logs depend on the rig's calibration, so the assertion is that
they move when the stick moves and settle when it is released.
"""

import re
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from v3xctrl_e2e.log_expectations import LogRecord, LogSource, control_values, count, find, slice_between
from v3xctrl_e2e.virtual_gamepad import Axis, Button, VirtualGamepad


class StepKind(StrEnum):
    AXIS = "axis"
    PRESS = "press"


@dataclass(frozen=True)
class Step:
    phase: str
    kind: StepKind
    seconds: float
    axis: Axis | None = None
    value: float = 0.0
    button: Button | None = None


BUTTON_HOLD_SECONDS = 0.15
PULSE_WIDTH_CHANGE_MICROSECONDS = 20.0

SCENARIO: tuple[Step, ...] = (
    Step("throttle-forward", StepKind.AXIS, 2.0, axis=Axis.THROTTLE, value=0.5),
    Step("throttle-release", StepKind.AXIS, 1.5, axis=Axis.THROTTLE, value=0.0),
    Step("steering-left", StepKind.AXIS, 1.5, axis=Axis.STEERING, value=-0.5),
    Step("steering-right", StepKind.AXIS, 1.5, axis=Axis.STEERING, value=0.5),
    Step("steering-release", StepKind.AXIS, 1.5, axis=Axis.STEERING, value=0.0),
    Step("trim-up-1", StepKind.PRESS, 0.7, button=Button.TRIM_INCREASE),
    Step("trim-up-2", StepKind.PRESS, 0.7, button=Button.TRIM_INCREASE),
    Step("trim-down-1", StepKind.PRESS, 0.7, button=Button.TRIM_DECREASE),
    Step("trim-down-2", StepKind.PRESS, 0.7, button=Button.TRIM_DECREASE),
    Step("recording-start", StepKind.PRESS, 3.0, button=Button.REC_TOGGLE),
    # The streamer gives a stop five seconds to flush before forcing teardown,
    # and the outcome must land in the journal before the scenario ends.
    Step("recording-stop", StepKind.PRESS, 8.0, button=Button.REC_TOGGLE),
)


@dataclass(frozen=True)
class PhaseWindow:
    phase: str
    start: float
    end: float


def run_scenario(
    gamepad: VirtualGamepad,
    steps: tuple[Step, ...],
    clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> list[PhaseWindow]:
    """Drive the gamepad through `steps`, returning when each phase was active on the harness clock."""
    windows: list[PhaseWindow] = []

    for step in steps:
        start = clock()
        match step.kind:
            case StepKind.AXIS if step.axis is not None:
                gamepad.set_axis(step.axis, step.value)
            case StepKind.PRESS if step.button is not None:
                gamepad.press(step.button)
                sleep(BUTTON_HOLD_SECONDS)
                gamepad.release(step.button)

        sleep(step.seconds)
        windows.append(PhaseWindow(step.phase, start, clock()))

    gamepad.release_all()
    return windows


def _window(windows: list[PhaseWindow], phase: str) -> PhaseWindow:
    for window in windows:
        if window.phase == phase:
            return window

    raise KeyError(phase)


def _values_in(records: list[LogRecord], windows: list[PhaseWindow], phase: str) -> tuple[list[float], list[float]]:
    window = _window(windows, phase)
    values = control_values(slice_between(records, window.start, window.end))
    return [value.throttle for value in values], [value.steering for value in values]


def _settled_value(values: list[float]) -> float | None:
    """The pulse width a phase settled on: the median of the second half of its window.

    The windows run on the harness clock while the values carry the streamer's
    journal time, and the two can sit a few hundred milliseconds apart. The
    first half of a window may still show the previous phase, the second half
    is the phase itself.
    """
    if not values:
        return None

    settled = values[len(values) // 2 :]
    return statistics.median(settled)


def assess_axes(records: list[LogRecord], windows: list[PhaseWindow]) -> list[str]:
    failures: list[str] = []

    throttle_forward, _ = _values_in(records, windows, "throttle-forward")
    throttle_release, _ = _values_in(records, windows, "throttle-release")
    _, steering_left = _values_in(records, windows, "steering-left")
    _, steering_right = _values_in(records, windows, "steering-right")
    _, steering_release = _values_in(records, windows, "steering-release")

    throttle_idle = _settled_value(throttle_release)
    steering_idle = _settled_value(steering_release)
    throttle_held = _settled_value(throttle_forward)
    left_held = _settled_value(steering_left)
    right_held = _settled_value(steering_right)

    if throttle_idle is None or throttle_held is None:
        failures.append("input: no control values logged by the streamer during the throttle phases")
    else:
        moved = abs(throttle_held - throttle_idle)
        if moved < PULSE_WIDTH_CHANGE_MICROSECONDS:
            failures.append(f"input: throttle pulse width moved {moved:.0f}us from idle {throttle_idle:.0f}us")

        if abs(throttle_release[-1] - throttle_idle) > PULSE_WIDTH_CHANGE_MICROSECONDS:
            failures.append(f"input: throttle did not settle, last value {throttle_release[-1]:.0f}us")

    if steering_idle is None or left_held is None or right_held is None:
        failures.append("input: no control values logged by the streamer during the steering phases")
    else:
        left = abs(left_held - steering_idle)
        right = abs(right_held - steering_idle)
        if left < PULSE_WIDTH_CHANGE_MICROSECONDS or right < PULSE_WIDTH_CHANGE_MICROSECONDS:
            failures.append(f"input: steering pulse width moved {left:.0f}us left and {right:.0f}us right")
        elif (left_held - steering_idle) * (right_held - steering_idle) >= 0:
            failures.append(
                "input: steering left and right moved the pulse width in the same direction, "
                f"{left_held:.0f}us and {right_held:.0f}us from idle {steering_idle:.0f}us"
            )

        if abs(steering_release[-1] - steering_idle) > PULSE_WIDTH_CHANGE_MICROSECONDS:
            failures.append(f"input: steering did not settle, last value {steering_release[-1]:.0f}us")

    return failures


def assess_commands(records: list[LogRecord]) -> list[str]:
    checks: list[tuple[str, LogSource, str, int]] = [
        ("trim increase sent", LogSource.VIEWER, r"Sending command: trim \{'action': 'increase'\}", 2),
        ("trim decrease sent", LogSource.VIEWER, r"Sending command: trim \{'action': 'decrease'\}", 2),
        ("recording start sent", LogSource.VIEWER, r"Sending command: recording \{'action': 'start'\}", 1),
        ("recording stop sent", LogSource.VIEWER, r"Sending command: recording \{'action': 'stop'\}", 1),
        ("command acknowledged", LogSource.VIEWER, r"Received command ack: True", 6),
        ("trim received", LogSource.CONTROL, r"Received command: .*trim", 4),
        ("recording received", LogSource.CONTROL, r"Received command: .*recording", 2),
        ("recording started", LogSource.VIDEO, r"Recording started:", 1),
        ("recording stopped", LogSource.VIDEO, r"Recording stopped:", 1),
    ]

    failures: list[str] = []
    for description, source, pattern, minimum in checks:
        seen = count(records, source, pattern)
        if seen < minimum:
            failures.append(f"input: {description}: expected at least {minimum}, saw {seen}")

    if count(records, LogSource.VIDEO, r"Recording stop timed out") > 0:
        failures.append("input: the streamer forced the recording teardown after its stop timeout")

    return failures


def assess_scenario(records: list[LogRecord], windows: list[PhaseWindow]) -> list[str]:
    return assess_axes(records, windows) + assess_commands(records)


RECORDING_STOPPED_PATTERN = re.compile(r"Recording stopped(?: \(forced\))?: (?P<path>\S+)")


def recording_paths(records: list[LogRecord]) -> list[str]:
    """The files the streamer reports having recorded, for cleanup."""
    paths: list[str] = []
    for record in find(records, LogSource.VIDEO, RECORDING_STOPPED_PATTERN.pattern):
        match = RECORDING_STOPPED_PATTERN.search(record.text)
        if match is not None and match["path"] != "unknown":
            paths.append(match["path"])

    return paths
