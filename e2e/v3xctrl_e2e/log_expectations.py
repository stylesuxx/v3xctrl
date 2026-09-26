"""Pattern matching and statistics parsing over captured log lines.

Everything here is a pure function over `LogRecord` values, so the harness
logic can be tested on captured text without a viewer or a streamer.
"""

import re
from dataclasses import dataclass
from enum import StrEnum


class LogSource(StrEnum):
    VIEWER = "viewer"
    SPECTATOR = "spectator"
    SERVICE_MANAGER = "v3xctrl-service-manager"
    VIDEO = "v3xctrl-video"
    CONTROL = "v3xctrl-control"


JOURNAL_UNITS: tuple[LogSource, ...] = (LogSource.SERVICE_MANAGER, LogSource.VIDEO, LogSource.CONTROL)


@dataclass(frozen=True)
class LogRecord:
    """One captured line. `captured_at` is the harness monotonic clock at capture."""

    source: LogSource
    text: str
    captured_at: float


@dataclass(frozen=True)
class Required:
    description: str
    source: LogSource
    pattern: str
    minimum_count: int = 1


@dataclass(frozen=True)
class Forbidden:
    description: str
    source: LogSource
    pattern: str
    allowed: tuple[str, ...] = ()


def find(records: list[LogRecord], source: LogSource, pattern: str) -> list[LogRecord]:
    expression = re.compile(pattern)
    return [record for record in records if record.source == source and expression.search(record.text)]


def count(records: list[LogRecord], source: LogSource, pattern: str) -> int:
    return len(find(records, source, pattern))


def is_satisfied(records: list[LogRecord], required: Required) -> bool:
    return count(records, required.source, required.pattern) >= required.minimum_count


def evaluate(records: list[LogRecord], required: list[Required], forbidden: list[Forbidden]) -> list[str]:
    """Return one failure message per unmet requirement or forbidden hit."""
    failures: list[str] = []

    for requirement in required:
        seen = count(records, requirement.source, requirement.pattern)
        if seen < requirement.minimum_count:
            failures.append(
                f"{requirement.description}: expected at least {requirement.minimum_count} "
                f"'{requirement.pattern}' in {requirement.source}, saw {seen}"
            )

    for rule in forbidden:
        allowed = [re.compile(pattern) for pattern in rule.allowed]
        hits = [
            record
            for record in find(records, rule.source, rule.pattern)
            if not any(expression.search(record.text) for expression in allowed)
        ]
        if hits:
            failures.append(_forbidden_failure(rule, hits))

    return failures


LOG_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d\d-\d\d (?P<time>\d\d:\d\d:\d\d),\d{3}")


def _log_time(text: str) -> str | None:
    match = LOG_TIMESTAMP_PATTERN.match(text)
    return None if match is None else match["time"]


def _forbidden_failure(rule: Forbidden, hits: list[LogRecord]) -> str:
    """One line per rule: the offending line, or the count and span when it repeats."""
    first = hits[0]
    if len(hits) == 1:
        return f"{rule.description}: {rule.source}: {first.text}"

    first_time, last_time = _log_time(first.text), _log_time(hits[-1].text)
    span = f" from {first_time} to {last_time}" if first_time and last_time else ""
    return f"{rule.description}: {len(hits)} times{span}, first: {rule.source}: {first.text}"


def slice_after(records: list[LogRecord], captured_at: float) -> list[LogRecord]:
    return [record for record in records if record.captured_at >= captured_at]


def slice_between(records: list[LogRecord], start: float, end: float) -> list[LogRecord]:
    return [record for record in records if start <= record.captured_at <= end]


@dataclass(frozen=True)
class ReceiverStats:
    frames: int
    dropped_empty: int
    dropped_old: int
    dropped_burst: int
    drop_rate: float
    avg_decoded_fps: int
    avg_rendered_fps: int
    avg_jitter: float
    max_jitter: float


RECEIVER_STATS_PATTERN = re.compile(
    r"Receiver\w*: frames=(?P<frames>\d+), dropped_empty=(?P<dropped_empty>\d+), "
    r"dropped_old=(?P<dropped_old>\d+), dropped_burst=(?P<dropped_burst>\d+), "
    r"drop_rate=(?P<drop_rate>[\d.]+)%, avg_decoded_fps=(?P<avg_decoded_fps>\d+), "
    r"avg_rendered_fps=(?P<avg_rendered_fps>\d+), avg_jitter=(?P<avg_jitter>[\d.]+)ms, "
    r"max_jitter=(?P<max_jitter>[\d.]+)ms"
)

TELEMETRY_COUNT_PATTERN = re.compile(r"Telemetry: (?P<count>\d+) messages in last (?P<seconds>\d+)s")

# The streamer logs the mixer output of every control message, as
# "Channel A: ...; Channel B: ..." on current builds and as
# "Throttle: ...; Steering: ..." on builds from before the differential mixer.
# The axis checks read channel A as throttle and channel B as steering, which
# holds for the Ackermann mixer.
CONTROL_VALUES_PATTERN = re.compile(
    r"(?:Throttle|Channel A): (?P<throttle>-?[\d.]+); (?:Steering|Channel B): (?P<steering>-?[\d.]+)"
)


def parse_receiver_stats(text: str) -> ReceiverStats | None:
    match = RECEIVER_STATS_PATTERN.search(text)
    if match is None:
        return None

    return ReceiverStats(
        frames=int(match["frames"]),
        dropped_empty=int(match["dropped_empty"]),
        dropped_old=int(match["dropped_old"]),
        dropped_burst=int(match["dropped_burst"]),
        drop_rate=float(match["drop_rate"]),
        avg_decoded_fps=int(match["avg_decoded_fps"]),
        avg_rendered_fps=int(match["avg_rendered_fps"]),
        avg_jitter=float(match["avg_jitter"]),
        max_jitter=float(match["max_jitter"]),
    )


@dataclass(frozen=True)
class TelemetryCount:
    messages: int
    seconds: int

    @property
    def rate_hz(self) -> float:
        return self.messages / self.seconds if self.seconds > 0 else 0.0


def parse_telemetry_count(text: str) -> TelemetryCount | None:
    match = TELEMETRY_COUNT_PATTERN.search(text)
    if match is None:
        return None

    return TelemetryCount(messages=int(match["count"]), seconds=int(match["seconds"]))


@dataclass(frozen=True)
class ControlValues:
    throttle: float
    steering: float


def parse_control_values(text: str) -> ControlValues | None:
    match = CONTROL_VALUES_PATTERN.search(text)
    if match is None:
        return None

    return ControlValues(throttle=float(match["throttle"]), steering=float(match["steering"]))


CONTROL_HOLD_PATTERN = re.compile(r"Control resumed after (?P<seconds>[\d.]+)s")


def control_holds(records: list[LogRecord]) -> list[float]:
    """The failsafe holds the streamer reported, in seconds, in log order."""
    holds: list[float] = []
    for record in records:
        if record.source != LogSource.CONTROL:
            continue

        match = CONTROL_HOLD_PATTERN.search(record.text)
        if match is not None:
            holds.append(float(match["seconds"]))

    return holds


def describe_control_holds(holds: list[float], window_seconds: float) -> str:
    per_minute = len(holds) * 60 / window_seconds if window_seconds > 0 else 0.0
    return f"control holds: {len(holds)} in {window_seconds:.0f}s ({per_minute:.1f}/min), longest {max(holds) * 1000:.0f} ms"


def receiver_stats(records: list[LogRecord], source: LogSource = LogSource.VIEWER) -> list[ReceiverStats]:
    stats = (parse_receiver_stats(record.text) for record in records if record.source == source)
    return [entry for entry in stats if entry is not None]


def telemetry_counts(records: list[LogRecord], window_start: float | None = None) -> list[TelemetryCount]:
    """Count lines whose whole counting window lies after `window_start`.

    A count line covers the seconds before it was logged, so the first one
    after connecting straddles the connection phase and says nothing about
    the steady state.
    """
    counts: list[TelemetryCount] = []
    for record in records:
        if record.source != LogSource.VIEWER:
            continue

        entry = parse_telemetry_count(record.text)
        if entry is None:
            continue

        if window_start is not None and record.captured_at - entry.seconds < window_start:
            continue

        counts.append(entry)

    return counts


def control_values(records: list[LogRecord]) -> list[ControlValues]:
    values = (parse_control_values(record.text) for record in records if record.source == LogSource.CONTROL)
    return [entry for entry in values if entry is not None]


def is_pipeline_start(entry: ReceiverStats) -> bool:
    """The receiver logs a stats line on its first frame; it covers no interval."""
    return entry.frames <= 1 and entry.avg_decoded_fps == 0


def full_windows(stats: list[ReceiverStats]) -> list[ReceiverStats]:
    return [entry for entry in stats if not is_pipeline_start(entry)]


def check_video_flow(
    stats: list[ReceiverStats],
    minimum_fps: int,
    maximum_drop_rate: float,
    consecutive_low_windows: int = 1,
) -> list[str]:
    """Stats lines only appear while frames arrive, so their presence is the flow signal.

    The receiver logs one line every 10 s, so a 20 s window holds one or two
    full lines depending on where it starts; the video gap rule covers the
    rest of the window. A frame rate below the floor fails once it lasts
    `consecutive_low_windows` stats windows in a row; a soak over the internet
    relay tolerates a single slow window that way.
    """
    windows = full_windows(stats)
    if not windows:
        return [f"video flow: expected at least 1 full receiver stats line, saw {len(windows)}"]

    failures: list[str] = []
    low_run = 0
    for entry in windows:
        if entry.avg_decoded_fps < minimum_fps:
            low_run += 1
            if low_run == consecutive_low_windows:
                failures.append(
                    f"video flow: avg_decoded_fps {entry.avg_decoded_fps} below {minimum_fps}"
                    + (f" for {low_run} windows in a row" if consecutive_low_windows > 1 else "")
                )
        else:
            low_run = 0

        if entry.drop_rate > maximum_drop_rate:
            failures.append(f"video flow: drop_rate {entry.drop_rate}% above {maximum_drop_rate}%")

    return failures


def lowest_fps(stats: list[ReceiverStats]) -> int | None:
    """The slowest full stats window, for the notes of a long hold."""
    windows = full_windows(stats)
    if not windows:
        return None

    return min(entry.avg_decoded_fps for entry in windows)


def check_telemetry_rate(counts: list[TelemetryCount], expected_hz: float, tolerance: float) -> list[str]:
    """Each count line must sit within `tolerance` (a fraction) of the expected rate."""
    if not counts:
        return ["telemetry rate: no telemetry count lines"]

    failures: list[str] = []
    lower = expected_hz * (1.0 - tolerance)
    for entry in counts:
        if entry.rate_hz < lower:
            failures.append(
                f"telemetry rate: {entry.messages} messages in {entry.seconds}s is {entry.rate_hz:.2f} Hz, "
                f"below {lower:.2f} Hz"
            )

    return failures
