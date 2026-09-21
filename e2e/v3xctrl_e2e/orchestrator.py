"""Runs the matrix: one viewer process and one streamer configuration per test case."""

import logging
import socket
import threading
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from v3xctrl_e2e.artifacts import RunDirectory, TestResult, write_test_artifacts
from v3xctrl_e2e.expectations import Expectations, expectations_for, failure_expectations_for
from v3xctrl_e2e.input_scenario import SCENARIO, assess_scenario, recording_paths, run_scenario
from v3xctrl_e2e.log_expectations import (
    LogRecord,
    LogSource,
    Required,
    check_telemetry_rate,
    check_video_flow,
    evaluate,
    is_satisfied,
    lowest_fps,
    receiver_stats,
    slice_after,
    slice_between,
    telemetry_counts,
)
from v3xctrl_e2e.matrix import Phase, TestCase
from v3xctrl_e2e.streamer_client import StreamerClient
from v3xctrl_e2e.streamer_config import (
    build_streamer_config,
    load_shipped_defaults,
    source_framerate,
    telemetry_send_rate,
)
from v3xctrl_e2e.viewer_config import (
    GamepadBinding,
    build_spectator_settings,
    build_viewer_settings,
    render_settings,
)
from v3xctrl_e2e.viewer_launcher import ViewerKind, ViewerLauncher, ViewerProcess
from v3xctrl_e2e.virtual_gamepad import VirtualGamepad

logger = logging.getLogger(__name__)

VIDEO_UNIT = "v3xctrl-video"
CONTROL_UNIT = "v3xctrl-control"

VIDEO_GAP_TIMEOUT_SECONDS = 20.0
VIDEO_RESUME_TIMEOUT_SECONDS = 60.0
CONTROL_GAP_TIMEOUT_SECONDS = 25.0
CONTROL_RESUME_TIMEOUT_SECONDS = 40.0
JOURNAL_SETTLE_SECONDS = 3.0
POLL_INTERVAL_SECONDS = 0.5
WRONG_ID_APPLY_TIMEOUT_SECONDS = 15.0


class ServiceAction(StrEnum):
    STOP = "stop"
    START = "start"


# Telemetry count windows are anchored on the first telemetry message, which is
# also the last connection signal, so the first count line may start a poll
# interval before the steady window does.
TELEMETRY_WINDOW_GRACE_SECONDS = 2.0
# Beyond this the two clocks disagree rather than the line being late.
MAXIMUM_JOURNAL_LATENCY_SECONDS = 10.0
# A soak over the internet relay fails on a sustained frame rate drop, not on one slow window.
SOAK_CONSECUTIVE_LOW_WINDOWS = 2
# Time between stopping the viewer and starting the spectator on its ports.
VIEWER_HANDOVER_SECONDS = 2.0
# The relay keeps a peer registration for RelayServer.TIMEOUT (450 s) and
# cleans up every 10 s; a spectator whose viewer left has to be cut off by then.
RELAY_PEER_TIMEOUT_SECONDS = 450.0
VIEWER_LEAVES_HOLD_SECONDS = RELAY_PEER_TIMEOUT_SECONDS + 30.0
SPECTATOR_WARMUP_SECONDS = 20.0


@dataclass(frozen=True)
class RunOptions:
    streamer_host: str | None
    ssh_user: str | None
    relay_host: str
    relay_id: str
    phases: set[Phase]
    include_negative: bool = False
    viewer_kind: ViewerKind = ViewerKind.SOURCE
    viewer_python: str = "python3"
    headless: bool = False
    use_camera: bool = False
    spectator_id: str = ""
    spectator_seconds: float = 60.0
    case_names: list[str] = field(default_factory=list)
    with_gamepad: bool = True
    steady_seconds: float = 20.0
    connect_timeout: float = 45.0
    apply_timeout: float = 90.0
    minimum_fps: int | None = None
    maximum_drop_rate: float = 10.0
    telemetry_tolerance: float = 0.2
    maximum_load_per_cpu: float = 0.75
    video_port: int = 16384
    control_port: int = 16386
    runs_directory: Path = field(default_factory=lambda: Path("runs"))
    viewer_source: Path | None = None


class RecordStore:
    """Thread-safe timeline of viewer lines and streamer journal lines.

    Journal lines reach the harness a few hundred milliseconds after journald
    stamped them (journald batching, ssh, the agent). Both machines run NTP, so
    the journal's realtime stamp is used to place each line where it happened
    on the harness clock; otherwise a 1.5 s input step spills into the next.
    """

    def __init__(self, clock: Callable[[], float], wall_clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._wall_clock = wall_clock
        self._lock = threading.Lock()
        self._records: list[LogRecord] = []

    def append(self, record: LogRecord) -> None:
        with self._lock:
            self._records.append(record)

    def on_agent_event(self, event: dict[str, Any]) -> None:
        if event.get("event") != "journal":
            return

        unit = str(event.get("unit", ""))
        try:
            source = LogSource(unit)
        except ValueError:
            return

        self.append(LogRecord(source, str(event.get("message", "")), self._captured_at(event)))

    def _captured_at(self, event: dict[str, Any]) -> float:
        now = self._clock()
        realtime_microseconds = event.get("realtime")
        if not isinstance(realtime_microseconds, int) or realtime_microseconds <= 0:
            return now

        latency = self._wall_clock() - realtime_microseconds / 1_000_000
        if latency <= 0 or latency > MAXIMUM_JOURNAL_LATENCY_SECONDS:
            return now

        return now - latency

    def snapshot(self) -> list[LogRecord]:
        with self._lock:
            return list(self._records)


def viewer_lan_address(streamer_host: str) -> str:
    """The local address the streamer will reach the viewer on. No packet is sent."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((streamer_host, 9))
        address: str = probe.getsockname()[0]
        return address


class Orchestrator:
    def __init__(
        self,
        options: RunOptions,
        client: StreamerClient | None,
        launcher: ViewerLauncher,
        run_directory: RunDirectory,
        gamepad: VirtualGamepad | None,
        gamepad_binding: GamepadBinding | None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.options = options
        self.client = client
        self.launcher = launcher
        self.run_directory = run_directory
        self.gamepad = gamepad
        self.gamepad_binding = gamepad_binding
        self.clock = clock
        self.sleep = sleep

        self.store = RecordStore(clock)
        self._spectator: ViewerProcess | None = None
        self._spectator_title: str | None = None
        self._deleted_recordings: set[str] = set()
        self.shipped_defaults = load_shipped_defaults()
        self.viewer_host = viewer_lan_address(options.streamer_host) if options.streamer_host else None

    def on_agent_event(self, event: dict[str, Any]) -> None:
        self.store.on_agent_event(event)

    def run(self, test_cases: list[TestCase]) -> list[TestResult]:
        results: list[TestResult] = []
        uses_streamer = any(test_case.requires_streamer for test_case in test_cases)
        if uses_streamer and self.client is None:
            raise RuntimeError("the matrix needs a streamer but no streamer agent is connected")

        live_config: dict[str, Any] = {}
        if uses_streamer:
            live_config = self._require_client().open_run()

        try:
            for index, test_case in enumerate(test_cases, start=1):
                logger.info(f"{test_case.name}: starting")
                title = f"{test_case.name} ({index}/{len(test_cases)})"
                result = self.run_test(test_case, live_config, title)
                logger.info(
                    f"{test_case.name}: {'PASS' if result.passed else 'FAIL'} in {result.duration_seconds:.0f}s"
                )
                results.append(result)

        finally:
            if uses_streamer:
                restore = self._require_client().close_run(self.options.apply_timeout)
                logger.info(f"streamer config restored, services: {restore.get('states')}")

        return results

    def _require_client(self) -> StreamerClient:
        if self.client is None:
            raise RuntimeError("no streamer agent connected")

        return self.client

    def run_test(self, test_case: TestCase, live_config: dict[str, Any], title: str | None = None) -> TestResult:
        started = self.clock()
        self.store = RecordStore(self.clock)
        test_directory = self.run_directory.test_directory(test_case.name)
        failures: list[str] = []
        notes: list[str] = []

        binding = self.gamepad_binding if self.options.with_gamepad else None
        expectations = expectations_for(test_case, with_gamepad=binding is not None)

        # A fresh install has no settings file at all; the viewer must create it
        config_path = test_directory / "settings.toml"
        settings_text = ""
        if not test_case.bootstrap_without_config:
            settings = build_viewer_settings(
                test_case,
                self.options.relay_host,
                self.options.relay_id,
                binding,
                self.options.video_port,
                self.options.control_port,
            )
            settings_text = render_settings(settings)
            config_path.write_text(settings_text, encoding="utf-8")

        spectator_config_path: Path | None = None
        if test_case.with_spectator:
            if test_case.spectator_replaces_viewer:
                # Same machine, same ports as the viewer it replaces: the relay
                # then sees the spectator from the address it knows as the viewer.
                spectator_settings = build_spectator_settings(
                    test_case,
                    self.options.relay_host,
                    self.options.spectator_id,
                    self.options.video_port,
                    self.options.control_port,
                )
            else:
                spectator_settings = build_spectator_settings(
                    test_case, self.options.relay_host, self.options.spectator_id
                )
            spectator_config_path = test_directory / "spectator-settings.toml"
            spectator_config_path.write_text(render_settings(spectator_settings), encoding="utf-8")

        streamer_config: dict[str, Any] | None = None
        if test_case.requires_streamer:
            streamer_config = build_streamer_config(
                live_config,
                self.shipped_defaults,
                test_case,
                self.viewer_host or "",
                self.options.relay_host,
                self.options.relay_id,
                use_camera=self.options.use_camera,
            )

        viewer = self.launcher.start(config_path, test_directory / "viewer.log", self.store.append, title=title)
        self._deleted_recordings = set()
        self._spectator = None
        self._spectator_title = None if title is None else f"{title} spectator"

        try:
            if streamer_config is not None:
                # With a wrong relay ID the service manager refuses to start the
                # services, so there is nothing to wait for and nothing to flag.
                apply_timeout = (
                    WRONG_ID_APPLY_TIMEOUT_SECONDS if test_case.wrong_relay_id else self.options.apply_timeout
                )
                apply_result = self._require_client().begin_case(streamer_config, apply_timeout)
                notes.append(
                    f"streamer apply took {apply_result.get('seconds')}s, services {apply_result.get('states')}"
                )
                if not test_case.wrong_relay_id:
                    failures.extend(inactive_services(apply_result))

            if not test_case.is_expected_to_connect:
                failures.extend(self._run_negative(test_case))
            elif streamer_config is not None:
                failures.extend(
                    self._run_positive(
                        test_case, expectations, streamer_config, config_path, notes, spectator_config_path, viewer
                    )
                )
            else:
                failures.extend(self._run_viewer_only(test_case, expectations, config_path))

        except Exception as error:
            failures.append(f"harness error: {type(error).__name__}: {error}")

        finally:
            stop_requested_at = self.clock()
            if self._spectator is not None:
                notes.append(f"spectator exit code {self._spectator.stop()}")
                self._spectator = None

            exit_code = viewer.stop()
            notes.append(f"viewer exit code {exit_code}")
            if test_case.requires_streamer:
                self.sleep(JOURNAL_SETTLE_SECONDS)
                self._require_client().end_case()

        records = self.store.snapshot()
        if test_case.requires_streamer:
            failures.extend(self._delete_recordings(records))

        if test_case.is_expected_to_connect:
            # Tearing the viewer down produces error lines of its own (an aborted
            # relay registration, the streamer losing control), so forbidden
            # rules only cover the time the viewer was meant to be running.
            running_records = slice_between(records, started, stop_requested_at)
            failures.extend(evaluate(records, expectations.run, []))
            failures.extend(evaluate(running_records, [], expectations.forbidden))

        result = TestResult(
            name=test_case.name,
            passed=not failures,
            duration_seconds=round(self.clock() - started, 1),
            failures=failures,
            notes=notes,
        )
        write_test_artifacts(self.run_directory, result, records, streamer_config, settings_text)
        return result

    def _run_positive(
        self,
        test_case: TestCase,
        expectations: Expectations,
        streamer_config: dict[str, Any],
        config_path: Path,
        notes: list[str],
        spectator_config_path: Path | None = None,
        viewer: ViewerProcess | None = None,
    ) -> list[str]:
        failures: list[str] = []

        if not self._wait_for(expectations.connection, self.options.connect_timeout):
            failures.extend(evaluate(self.store.snapshot(), expectations.connection, []))
            return failures

        steady_seconds = self.options.steady_seconds
        viewer_replaced = False
        if spectator_config_path is not None and test_case.spectator_replaces_viewer and viewer is not None:
            notes.append(f"viewer stopped before the spectator started, exit code {viewer.stop()}")
            viewer_replaced = True
            self.sleep(VIEWER_HANDOVER_SECONDS)

        if spectator_config_path is not None:
            # The spectator joins a ready session; the relay's spectator timeout
            # is 30 s, so the hold has to be long enough to see it drop out.
            self._spectator = self.launcher.start(
                spectator_config_path,
                spectator_config_path.parent / "spectator.log",
                self.store.append,
                LogSource.SPECTATOR,
                title=self._spectator_title,
            )

            if not self._wait_for(expectations.spectator_connection, self.options.connect_timeout):
                failures.extend(evaluate(self.store.snapshot(), expectations.spectator_connection, []))
                return failures

            steady_seconds = self.options.spectator_seconds
            if test_case.viewer_leaves_after_spectator and viewer is not None:
                return self._run_viewer_leaves(viewer, notes)

            notes.append(f"spectator held for {steady_seconds:.0f}s")

        steady_start = self.clock()
        self.sleep(steady_seconds)
        steady_records = slice_between(self.store.snapshot(), steady_start, self.clock())

        failures.extend(evaluate(steady_records, [], expectations.steady_forbidden))
        minimum_fps = self.options.minimum_fps or max(source_framerate(streamer_config) - 5, 1)
        consecutive_low_windows = SOAK_CONSECUTIVE_LOW_WINDOWS if spectator_config_path is not None else 1
        viewer_stats = receiver_stats(steady_records)
        if not viewer_replaced:
            failures.extend(
                check_video_flow(viewer_stats, minimum_fps, self.options.maximum_drop_rate, consecutive_low_windows)
            )

        if spectator_config_path is not None:
            spectator_stats = receiver_stats(steady_records, LogSource.SPECTATOR)
            failures.extend(
                f"spectator {failure}"
                for failure in check_video_flow(
                    spectator_stats, minimum_fps, self.options.maximum_drop_rate, consecutive_low_windows
                )
            )
            notes.append(
                f"slowest window: viewer {lowest_fps(viewer_stats)} fps, spectator {lowest_fps(spectator_stats)} fps"
            )

        if not viewer_replaced:
            failures.extend(
                check_telemetry_rate(
                    telemetry_counts(steady_records, window_start=steady_start - TELEMETRY_WINDOW_GRACE_SECONDS),
                    telemetry_send_rate(streamer_config),
                    self.options.telemetry_tolerance,
                )
            )

        if test_case.bootstrap_without_config:
            failures.extend(check_bootstrapped_settings(config_path))

        if test_case.with_input_scenario:
            if self.gamepad is None or self.gamepad_binding is None:
                notes.append("input scenario skipped: no gamepad")
            else:
                failures.extend(self._run_input_scenario())

        if test_case.with_fault_injection:
            failures.extend(self._run_fault_injection())

        return failures

    def _run_viewer_leaves(self, viewer: ViewerProcess, notes: list[str]) -> list[str]:
        """Viewer and spectator are both connected; the viewer quits and the
        spectator must be cut off before the relay's registration lifetime ends."""
        # Let the spectator prove it receives video beside the viewer first.
        self.sleep(SPECTATOR_WARMUP_SECONDS)
        viewer_left_at = self.clock()
        notes.append(
            f"viewer stopped {SPECTATOR_WARMUP_SECONDS:.0f}s after the spectator joined, exit code {viewer.stop()}"
        )

        gap = Required("spectator cut off", LogSource.SPECTATOR, r"No frames received for")
        cut_off = self._wait_for([gap], VIEWER_LEAVES_HOLD_SECONDS)
        records = slice_after(self.store.snapshot(), viewer_left_at)

        if not cut_off:
            return [
                f"spectator still received video {VIEWER_LEAVES_HOLD_SECONDS:.0f}s after the viewer left; "
                f"the relay keeps forwarding to spectators without a viewer"
            ]

        first_gap = next(
            record for record in records if record.source == LogSource.SPECTATOR and "No frames received" in record.text
        )
        notes.append(f"spectator lost video {first_gap.captured_at - viewer_left_at:.0f}s after the viewer left")
        return []

    def _run_viewer_only(self, test_case: TestCase, expectations: Expectations, config_path: Path) -> list[str]:
        """No streamer: the viewer must come up, bind or reach the relay, and stay quiet."""
        failures: list[str] = []

        if not self._wait_for(expectations.connection, self.options.connect_timeout):
            failures.extend(evaluate(self.store.snapshot(), expectations.connection, []))

        steady_start = self.clock()
        self.sleep(self.options.steady_seconds)
        steady_records = slice_between(self.store.snapshot(), steady_start, self.clock())
        failures.extend(evaluate(steady_records, [], expectations.steady_forbidden))

        if test_case.bootstrap_without_config:
            failures.extend(check_bootstrapped_settings(config_path))

        return failures

    def _run_negative(self, test_case: TestCase) -> list[str]:
        """Wait for the expected failure lines, or hold the whole connect timeout
        when the case has none, then make sure no control channel came up."""
        required = failure_expectations_for(test_case)
        connected = Required("no connection", LogSource.VIEWER, r"Control channel connected")
        if required:
            self._wait_for(required, self.options.connect_timeout)
        else:
            self._wait_for([connected], self.options.connect_timeout)

        records = self.store.snapshot()

        failures = evaluate(records, required, [])
        if is_satisfied(records, connected):
            failures.append("negative test: the control channel connected although it was expected to fail")

        return failures

    def _run_input_scenario(self) -> list[str]:
        assert self.gamepad is not None
        scenario_start = self.clock()
        windows = run_scenario(self.gamepad, SCENARIO, self.clock, self.sleep)
        self.sleep(JOURNAL_SETTLE_SECONDS)

        records = slice_after(self.store.snapshot(), scenario_start)
        failures = assess_scenario(records, windows)
        failures.extend(self._delete_recordings(records))

        return failures

    def _delete_recordings(self, records: list[LogRecord]) -> list[str]:
        """Delete every recording the streamer reported in `records` and not yet deleted.

        A forced teardown lands in the journal seconds after the scenario, so
        the case end runs this a second time over all of the case's records.
        """
        failures: list[str] = []
        for path in recording_paths(records):
            if path in self._deleted_recordings:
                continue

            try:
                self._require_client().delete_recording(path)
                self._deleted_recordings.add(path)
            except Exception as error:
                failures.append(f"recording cleanup: {error}")

        return failures

    def _run_fault_injection(self) -> list[str]:
        failures: list[str] = []
        steps: list[tuple[ServiceAction, str, Required, float]] = [
            (
                ServiceAction.STOP,
                VIDEO_UNIT,
                Required("video gap detected", LogSource.VIEWER, r"No frames received for"),
                VIDEO_GAP_TIMEOUT_SECONDS,
            ),
            (
                ServiceAction.START,
                VIDEO_UNIT,
                Required("video resumed", LogSource.VIEWER, r"Video resumed after"),
                VIDEO_RESUME_TIMEOUT_SECONDS,
            ),
            (
                ServiceAction.STOP,
                CONTROL_UNIT,
                Required("control loss detected", LogSource.VIEWER, r"Control channel disconnected"),
                CONTROL_GAP_TIMEOUT_SECONDS,
            ),
            (
                ServiceAction.START,
                CONTROL_UNIT,
                Required("control reconnected", LogSource.VIEWER, r"Control channel connected", minimum_count=2),
                CONTROL_RESUME_TIMEOUT_SECONDS,
            ),
        ]

        for action, unit, requirement, timeout in steps:
            match action:
                case ServiceAction.STOP:
                    self._require_client().stop_service(unit)
                case ServiceAction.START:
                    self._require_client().start_service(unit)

            if not self._wait_for([requirement], timeout):
                failures.append(
                    f"fault injection: {requirement.description} not seen within {timeout:.0f}s after {action} {unit}"
                )

        return failures

    def _wait_for(self, required: list[Required], timeout: float) -> bool:
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            if self._is_satisfied(required):
                return True
            self.sleep(POLL_INTERVAL_SECONDS)

        return self._is_satisfied(required)

    def _is_satisfied(self, required: list[Required]) -> bool:
        records = self.store.snapshot()
        return all(is_satisfied(records, requirement) for requirement in required)


BOOTSTRAP_REQUIRED_KEYS = ("transport", "ports", "relay", "video", "widgets", "controls", "timing")


def inactive_services(apply_result: dict[str, Any]) -> list[str]:
    states: dict[str, str] = apply_result.get("states", {})
    return [f"streamer service {unit} is {state} after apply" for unit, state in states.items() if state != "active"]


def check_bootstrapped_settings(config_path: Path) -> list[str]:
    """Started without a settings file, the viewer must write a complete, parseable one."""
    if not config_path.exists():
        return ["bootstrap: the viewer did not create the settings file"]

    text = config_path.read_text(encoding="utf-8")
    if not text.strip():
        return ["bootstrap: the viewer created an empty settings file"]

    try:
        settings = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        return [f"bootstrap: written settings file does not parse: {error}"]

    missing = [key for key in BOOTSTRAP_REQUIRED_KEYS if key not in settings]
    if missing:
        return [f"bootstrap: written settings file lacks {', '.join(missing)}"]

    return []
