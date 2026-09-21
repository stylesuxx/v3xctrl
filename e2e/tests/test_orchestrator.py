import tempfile
import unittest
from pathlib import Path
from typing import Any

from v3xctrl_e2e.artifacts import RunDirectory
from v3xctrl_e2e.log_expectations import LogRecord, LogSource
from v3xctrl_e2e.matrix import (
    LOCAL_CASES,
    LOCAL_NEGATIVE_CASES,
    RELAY_NEGATIVE_CASES,
    SPECTATOR_CASES,
    VIEWER_CASES,
    Phase,
)
from v3xctrl_e2e.orchestrator import (
    Orchestrator,
    RecordStore,
    RunOptions,
    check_bootstrapped_settings,
    inactive_services,
)
from v3xctrl_e2e.viewer_launcher import ViewerKind

STATS = (
    "INFO - ReceiverGst: frames=300, dropped_empty=0, dropped_old=0, dropped_burst=0, drop_rate=0.0%, "
    "avg_decoded_fps=30, avg_rendered_fps=30, avg_jitter=1.0ms, max_jitter=2.0ms"
)

CONNECTED_VIEWER_LINES = [
    "INFO - GStreamer receiver available, will be used by default",
    "INFO - Using gst video receiver",
    "INFO - GStreamer receiver started on port 16384",
    "INFO - Control channel connected",
    "INFO - Pipeline is now PLAYING",
    "INFO - First telemetry message received",
]

STEADY_VIEWER_LINES = [STATS, STATS, "INFO - Telemetry: 10 messages in last 10s", STATS]

STREAMER_LINES = [
    (LogSource.VIDEO, "INFO - Building pipeline..."),
    (LogSource.CONTROL, "INFO - Connected"),
    (LogSource.VIDEO, "INFO - TcpTunnel connected to 192.168.1.100:16384"),
    (LogSource.CONTROL, "INFO - TcpTunnel connected to 192.168.1.100:16386"),
]


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.on_sleep: list[Any] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds
        for hook in list(self.on_sleep):
            hook()


class FakeViewerProcess:
    """Emits the shutdown lines when stopped, slightly after the stop was requested."""

    def __init__(self, clock: FakeClock, on_record, shutdown_lines: list[str]) -> None:
        self.clock = clock
        self.on_record = on_record
        self.shutdown_lines = shutdown_lines
        self.stopped = False

    def stop(self) -> int:
        self.stopped = True
        for line in self.shutdown_lines:
            self.on_record(LogRecord(LogSource.VIEWER, line, self.clock() + 0.1))
        return 0


class FakeLauncher:
    """Emits the connect lines on start and the steady lines on every sleep."""

    def __init__(
        self,
        clock: FakeClock,
        connect_lines: list[str],
        steady_lines: list[str],
        shutdown_lines: list[str] | None = None,
    ) -> None:
        self.clock = clock
        self.connect_lines = connect_lines
        self.steady_lines = steady_lines
        self.shutdown_lines = shutdown_lines or []
        self.spectator_connect_lines: list[str] = []
        self.spectator_steady_lines: list[str] = []
        self.started_with: list[Path] = []
        self.titles: list[str | None] = []
        self.processes: list[FakeViewerProcess] = []
        self.viewer_stopped_at_start: list[bool] = []

    def start(
        self,
        config_path: Path,
        log_path: Path,
        on_record,
        source: LogSource = LogSource.VIEWER,
        title: str | None = None,
    ) -> FakeViewerProcess:
        self.started_with.append(config_path)
        self.titles.append(title)
        self.viewer_stopped_at_start.append(bool(self.processes) and self.processes[0].stopped)
        if not config_path.exists():
            config_path.write_text('transport = "udp"\n[ports]\n[relay]\n[video]\n[widgets]\n[controls]\n[timing]\n')
        connect_lines = self.connect_lines if source == LogSource.VIEWER else self.spectator_connect_lines
        steady_lines = self.steady_lines if source == LogSource.VIEWER else self.spectator_steady_lines
        for line in connect_lines:
            on_record(LogRecord(source, line, self.clock()))

        def emit_steady() -> None:
            for line in steady_lines:
                on_record(LogRecord(source, line, self.clock()))

        self.clock.on_sleep.append(emit_steady)
        process = FakeViewerProcess(self.clock, on_record, self.shutdown_lines)
        self.processes.append(process)
        return process


class FakeClient:
    def __init__(self, on_event, clock: FakeClock, streamer_lines: list[tuple[LogSource, str]]) -> None:
        self.on_event = on_event
        self.clock = clock
        self.streamer_lines = streamer_lines
        self.applied_timeouts: list[float] = []
        self.apply_states = {"v3xctrl-video": "active", "v3xctrl-control": "active"}
        self.calls: list[tuple[str, Any]] = []
        self.applied: list[dict] = []

    def open_run(self) -> dict:
        self.calls.append(("open_run", None))
        return {"network": {"wifi": "keep"}, "viewer": {}, "video": {"resolution": "1280x720@30"}}

    def close_run(self, timeout: float) -> dict:
        self.calls.append(("close_run", timeout))
        return {"states": {}}

    def begin_case(self, config: dict, timeout: float) -> dict:
        self.calls.append(("begin_case", timeout))
        self.applied.append(config)
        self.applied_timeouts.append(timeout)
        for source, text in self.streamer_lines:
            self.on_event({"event": "journal", "unit": str(source), "message": text})
        return {"seconds": 3.0, "states": dict(self.apply_states)}

    def end_case(self) -> None:
        self.calls.append(("end_case", None))

    def stop_service(self, unit: str) -> dict:
        self.calls.append(("stop", unit))
        return {}

    def start_service(self, unit: str) -> dict:
        self.calls.append(("start", unit))
        return {}

    def delete_recording(self, path: str) -> None:
        self.calls.append(("delete_recording", path))


def options(**overrides: Any) -> RunOptions:
    values: dict[str, Any] = {
        "streamer_host": "127.0.0.1",
        "ssh_user": "chris",
        "relay_host": "relay.test:8888",
        "relay_id": "sid",
        "phases": {Phase.LOCAL},
        "with_gamepad": False,
        "steady_seconds": 20.0,
        "connect_timeout": 5.0,
    }
    values.update(overrides)
    return RunOptions(**values)


class OrchestratorTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.run_directory = RunDirectory(Path(self.temporary.name))
        self.clock = FakeClock()

    def tearDown(self):
        self.temporary.cleanup()

    def viewer_only(self, launcher: FakeLauncher, run_options: RunOptions) -> Orchestrator:
        return Orchestrator(
            run_options,
            None,
            launcher,  # type: ignore[arg-type]
            self.run_directory,
            gamepad=None,
            gamepad_binding=None,
            clock=self.clock,
            sleep=self.clock.sleep,
        )

    def build(self, connect_lines, steady_lines, streamer_lines, run_options=None):
        orchestrator_holder: list[Orchestrator] = []

        def on_event(event):
            orchestrator_holder[0].on_agent_event(event)

        client = FakeClient(on_event, self.clock, streamer_lines)
        launcher = FakeLauncher(self.clock, connect_lines, steady_lines)
        orchestrator = Orchestrator(
            run_options or options(),
            client,  # type: ignore[arg-type]
            launcher,  # type: ignore[arg-type]
            self.run_directory,
            gamepad=None,
            gamepad_binding=None,
            clock=self.clock,
            sleep=self.clock.sleep,
        )
        orchestrator_holder.append(orchestrator)
        return orchestrator, client, launcher


class TestHappyPath(OrchestratorTestCase):
    def test_direct_tcp_case_passes_and_restores_the_streamer(self):
        orchestrator, client, launcher = self.build(
            CONNECTED_VIEWER_LINES
            + ["INFO - TCP server listening on port 16384 (video)"] * 2
            + ["INFO - TCP client connected on port 16384 from x"] * 2,
            STEADY_VIEWER_LINES,
            STREAMER_LINES,
        )
        case = next(case for case in LOCAL_CASES if case.name == "L2-direct-tcp-tcp")

        results = orchestrator.run([case])

        self.assertEqual(results[0].failures, [])
        self.assertTrue(results[0].passed)
        self.assertEqual(client.calls[0], ("open_run", None))
        self.assertEqual(client.calls[-1], ("close_run", 90.0))
        self.assertEqual([name for name, _ in client.calls], ["open_run", "begin_case", "end_case", "close_run"])
        self.assertEqual(client.applied[0]["viewer"]["transport"], "tcp")
        self.assertEqual(client.applied[0]["network"], {"wifi": "keep"})
        self.assertEqual(launcher.titles, ["L2-direct-tcp-tcp (1/1)"])
        self.assertTrue((self.run_directory.path / case.name / "result.json").exists())
        self.assertTrue((self.run_directory.path / case.name / "timeline.log").exists())

    def test_recordings_reported_after_the_scenario_are_deleted_at_the_case_end(self):
        orchestrator, client, _ = self.build(
            CONNECTED_VIEWER_LINES
            + ["INFO - TCP server listening on port 16384 (video)"] * 2
            + ["INFO - TCP client connected on port 16384 from x"] * 2,
            STEADY_VIEWER_LINES,
            [*STREAMER_LINES, (LogSource.VIDEO, "WARNING - Recording stopped (forced): /data/recordings/stream-1.ts")],
        )
        case = next(case for case in LOCAL_CASES if case.name == "L2-direct-tcp-tcp")

        orchestrator.run([case])

        names = [name for name, _ in client.calls]
        self.assertEqual(names, ["open_run", "begin_case", "end_case", "delete_recording", "close_run"])
        self.assertIn(("delete_recording", "/data/recordings/stream-1.ts"), client.calls)

    def test_bootstrap_case_runs_without_a_streamer(self):
        launcher = FakeLauncher(self.clock, CONNECTED_VIEWER_LINES, STEADY_VIEWER_LINES)
        orchestrator = Orchestrator(
            options(streamer_host=None, ssh_user=None, phases={Phase.VIEWER}),
            None,
            launcher,  # type: ignore[arg-type]
            self.run_directory,
            gamepad=None,
            gamepad_binding=None,
            clock=self.clock,
            sleep=self.clock.sleep,
        )

        results = orchestrator.run([VIEWER_CASES[0]])

        self.assertEqual(results[0].failures, [])
        self.assertEqual(launcher.started_with[0].name, "settings.toml")
        self.assertFalse((self.run_directory.path / VIEWER_CASES[0].name / "streamer-config.json").exists())

    def test_streamer_case_without_a_client_is_refused(self):
        launcher = FakeLauncher(self.clock, CONNECTED_VIEWER_LINES, STEADY_VIEWER_LINES)
        orchestrator = self.viewer_only(launcher, options(streamer_host=None, ssh_user=None))

        with self.assertRaises(RuntimeError):
            orchestrator.run([LOCAL_CASES[0]])

    def test_viewer_relay_udp_case_passes_on_announcements(self):
        lines = [
            "INFO - Bound VIDEO socket to ('0.0.0.0', 16384)",
            "INFO - Bound CONTROL socket to ('0.0.0.0', 16386)",
            "DEBUG - Sent video announcement to relay.test:8888 from ('0.0.0.0', 16384)",
            "DEBUG - Sent control announcement to relay.test:8888 from ('0.0.0.0', 16386)",
        ]
        launcher = FakeLauncher(self.clock, lines, [])
        orchestrator = self.viewer_only(launcher, options(streamer_host=None, ssh_user=None, phases={Phase.VIEWER}))

        results = orchestrator.run([VIEWER_CASES[2]])

        self.assertEqual(results[0].failures, [])

    def test_errors_logged_while_shutting_down_are_ignored(self):
        lines = [
            "INFO - Bound VIDEO socket to x",
            "INFO - Bound CONTROL socket to x",
            "DEBUG - Sent video announcement to r",
            "DEBUG - Sent control announcement to r",
        ]
        shutdown = ["ERROR - Relay setup failed: Registration aborted"]
        launcher = FakeLauncher(self.clock, lines, [], shutdown_lines=shutdown)
        orchestrator = self.viewer_only(launcher, options(streamer_host=None, ssh_user=None, phases={Phase.VIEWER}))

        results = orchestrator.run([VIEWER_CASES[2]])

        self.assertEqual(results[0].failures, [])

    def test_viewer_relay_tcp_case_passes_once_the_tunnels_are_up(self):
        lines = [
            "INFO - GStreamer receiver available, will be used by default",
            "INFO - TCP relay tunnels started (video + control)",
            "INFO - TcpTunnel UDP proxy bound on ephemeral port 60494",
            "INFO - TcpTunnel UDP proxy bound on ephemeral port 34625",
            "INFO - Using gst video receiver",
            "INFO - GStreamer receiver started on port 16384",
        ]
        launcher = FakeLauncher(self.clock, lines, [])
        orchestrator = self.viewer_only(launcher, options(streamer_host=None, ssh_user=None, phases={Phase.VIEWER}))

        results = orchestrator.run([VIEWER_CASES[3]])

        self.assertEqual(results[0].failures, [])

    def test_viewer_relay_tcp_connect_failure_fails(self):
        lines = [
            "INFO - TCP relay tunnels started (video + control)",
            "INFO - TcpTunnel UDP proxy bound on ephemeral port 60494",
            "INFO - TcpTunnel UDP proxy bound on ephemeral port 34625",
            "INFO - Using gst video receiver",
            "INFO - GStreamer receiver started on port 16384",
        ]
        steady = ["DEBUG - TCP connect failed ([Errno 111] Connection refused), retrying in 1.0s..."]
        launcher = FakeLauncher(self.clock, lines, steady)
        orchestrator = self.viewer_only(launcher, options(streamer_host=None, ssh_user=None, phases={Phase.VIEWER}))

        results = orchestrator.run([VIEWER_CASES[3]])

        self.assertTrue(any("TCP connect attempt failed" in failure for failure in results[0].failures))

    def test_viewer_relay_rejection_fails(self):
        lines = [
            "INFO - Bound VIDEO socket to x",
            "INFO - Bound CONTROL socket to x",
            "DEBUG - Sent video announcement to r",
            "DEBUG - Sent control announcement to r",
        ]
        launcher = FakeLauncher(self.clock, lines, ["ERROR - Response Error: 403"])
        orchestrator = self.viewer_only(launcher, options(streamer_host=None, ssh_user=None, phases={Phase.VIEWER}))

        results = orchestrator.run([VIEWER_CASES[2]])

        self.assertTrue(any("relay rejected the viewer" in failure for failure in results[0].failures))

    def test_missing_connection_line_fails_with_the_requirement(self):
        lines = [line for line in CONNECTED_VIEWER_LINES if "PLAYING" not in line]
        orchestrator, _, _ = self.build(lines, STEADY_VIEWER_LINES, STREAMER_LINES[:2])
        case = next(case for case in LOCAL_CASES if case.name == "L1-direct-udp-udp")

        results = orchestrator.run([case])

        self.assertFalse(results[0].passed)
        self.assertTrue(any("video pipeline playing" in failure for failure in results[0].failures))

    def test_steady_window_faults_fail(self):
        case = next(case for case in LOCAL_CASES if case.name == "L2-direct-tcp-tcp")
        orchestrator, _, _ = self.build(
            [
                *CONNECTED_VIEWER_LINES,
                *["INFO - TCP server listening on port 16384 (video)"] * 2,
                *["INFO - TCP client connected on port 16384 from x"] * 2,
            ],
            [*STEADY_VIEWER_LINES, "ERROR - No message received for 10s"],
            STREAMER_LINES,
        )

        results = orchestrator.run([case])

        self.assertTrue(any("control timeout during steady window" in failure for failure in results[0].failures))

    def test_fault_injection_drives_the_services(self):
        clock = self.clock
        events: list[str] = []

        class FaultClient(FakeClient):
            def stop_service(self, unit: str) -> dict:
                events.append(f"stop {unit}")
                text = (
                    "INFO - No frames received for 5.0s, clearing frame"
                    if "video" in unit
                    else "INFO - Control channel disconnected"
                )
                orchestrator.store.append(LogRecord(LogSource.VIEWER, text, clock()))
                return {}

            def start_service(self, unit: str) -> dict:
                events.append(f"start {unit}")
                text = "INFO - Video resumed after 6.0s" if "video" in unit else "INFO - Control channel connected"
                orchestrator.store.append(LogRecord(LogSource.VIEWER, text, clock()))
                return {}

        holder: list[Orchestrator] = []
        client = FaultClient(lambda event: holder[0].on_agent_event(event), clock, STREAMER_LINES[:2])
        launcher = FakeLauncher(clock, CONNECTED_VIEWER_LINES, STEADY_VIEWER_LINES)
        orchestrator = Orchestrator(options(), client, launcher, self.run_directory, None, None, clock, clock.sleep)  # type: ignore[arg-type]
        holder.append(orchestrator)
        case = next(case for case in LOCAL_CASES if case.name == "L1-direct-udp-udp")

        results = orchestrator.run([case])

        self.assertEqual(
            events, ["stop v3xctrl-video", "start v3xctrl-video", "stop v3xctrl-control", "start v3xctrl-control"]
        )
        self.assertEqual([failure for failure in results[0].failures if "fault injection" in failure], [])
        self.assertIn("input scenario skipped: no gamepad", results[0].notes)


SPECTATOR_CONNECT_LINES = [
    "INFO - Received PeerInfo for video: PeerInfo(...)",
    "INFO - Received PeerInfo for control: PeerInfo(...)",
    "INFO - Using gst video receiver",
    "INFO - Pipeline is now PLAYING",
]

RELAY_VIEWER_LINES = [
    *CONNECTED_VIEWER_LINES,
    "INFO - Received PeerInfo for video: PeerInfo(...)",
    "INFO - Received PeerInfo for control: PeerInfo(...)",
]

RELAY_STREAMER_LINES = [
    (LogSource.VIDEO, "INFO - Building pipeline..."),
    (LogSource.CONTROL, "INFO - Connected"),
    (LogSource.SERVICE_MANAGER, "INFO - Received PeerInfo for video: PeerInfo(...)"),
    (LogSource.SERVICE_MANAGER, "INFO - Received PeerInfo for control: PeerInfo(...)"),
]


class TestSpectator(OrchestratorTestCase):
    def build_spectator(self, spectator_steady_lines: list[str]):
        run_options = options(phases={Phase.RELAY}, spectator_id="spec", spectator_seconds=120.0)
        orchestrator, client, launcher = self.build(
            RELAY_VIEWER_LINES, STEADY_VIEWER_LINES, RELAY_STREAMER_LINES, run_options
        )
        launcher.spectator_connect_lines = SPECTATOR_CONNECT_LINES
        launcher.spectator_steady_lines = spectator_steady_lines
        return orchestrator, client, launcher

    def test_spectator_joins_and_holds(self):
        orchestrator, _, launcher = self.build_spectator([STATS, STATS])
        started = self.clock()

        results = orchestrator.run([SPECTATOR_CASES[0]])

        self.assertEqual(results[0].failures, [])
        self.assertEqual(len(launcher.started_with), 2)
        self.assertTrue(str(launcher.started_with[1]).endswith("spectator-settings.toml"))
        self.assertEqual(launcher.titles, ["R6-relay-udp-spectator (1/1)", "R6-relay-udp-spectator (1/1) spectator"])
        self.assertGreaterEqual(self.clock() - started, 120.0)
        self.assertTrue(any("spectator held for 120s" in note for note in results[0].notes))

    def test_spectator_video_gap_fails(self):
        orchestrator, _, _ = self.build_spectator([STATS, "INFO - No frames received for 5.0s, clearing frame"])

        results = orchestrator.run([SPECTATOR_CASES[0]])

        self.assertTrue(any("spectator video gap" in failure for failure in results[0].failures))

    def test_spectator_low_fps_is_reported_separately(self):
        low = STATS.replace("avg_decoded_fps=30", "avg_decoded_fps=5")
        orchestrator, _, _ = self.build_spectator([STATS, low, low])

        results = orchestrator.run([SPECTATOR_CASES[0]])

        self.assertTrue(any(failure.startswith("spectator video flow") for failure in results[0].failures))

    def test_spectator_single_slow_window_is_only_noted(self):
        low = STATS.replace("avg_decoded_fps=30", "avg_decoded_fps=21")
        orchestrator, _, _ = self.build_spectator([STATS, low, STATS])

        results = orchestrator.run([SPECTATOR_CASES[0]])

        self.assertEqual(results[0].failures, [])
        self.assertTrue(any("slowest window" in note and "spectator 21 fps" in note for note in results[0].notes))

    def test_replacing_spectator_starts_after_the_viewer_stopped_on_its_ports(self):
        orchestrator, _, launcher = self.build_spectator([STATS, STATS])

        results = orchestrator.run([SPECTATOR_CASES[2]])

        self.assertEqual(results[0].failures, [])
        self.assertEqual(launcher.viewer_stopped_at_start, [False, True])
        settings = launcher.started_with[1].read_text()
        self.assertIn("video = 16384", settings)
        self.assertIn("control = 16386", settings)
        self.assertTrue(any("viewer stopped before the spectator" in note for note in results[0].notes))

    def test_replacing_spectator_tolerates_the_streamer_losing_its_viewer(self):
        orchestrator, client, _ = self.build_spectator([STATS, STATS])
        client.streamer_lines = [
            *RELAY_STREAMER_LINES,
            (LogSource.CONTROL, "ERROR - No message received for 0.15s"),
            (LogSource.CONTROL, "INFO - Disconnected"),
        ]

        results = orchestrator.run([SPECTATOR_CASES[2]])

        self.assertEqual(results[0].failures, [])

    def test_replacing_spectator_video_gap_fails(self):
        orchestrator, _, _ = self.build_spectator([STATS, "INFO - No frames received for 5.0s, clearing frame"])

        results = orchestrator.run([SPECTATOR_CASES[2]])

        self.assertTrue(any("spectator video gap" in failure for failure in results[0].failures))

    def test_viewer_leaves_and_spectator_is_cut_off(self):
        orchestrator, _, launcher = self.build_spectator([STATS, STATS])
        stop_time: list[float] = []

        def emit_gap_after_viewer_stop() -> None:
            if launcher.processes and launcher.processes[0].stopped and not stop_time:
                stop_time.append(self.clock())
                orchestrator.store.append(
                    LogRecord(
                        LogSource.SPECTATOR, "INFO - No frames received for 5.0s, clearing frame", self.clock() + 12.0
                    )
                )

        self.clock.on_sleep.append(emit_gap_after_viewer_stop)

        results = orchestrator.run([SPECTATOR_CASES[3]])

        self.assertEqual(results[0].failures, [])
        self.assertTrue(any("lost video 12s after the viewer left" in note for note in results[0].notes))

    def test_viewer_leaves_and_spectator_keeps_watching_fails(self):
        orchestrator, _, _ = self.build_spectator([STATS, STATS])

        results = orchestrator.run([SPECTATOR_CASES[3]])

        self.assertEqual(len(results[0].failures), 1)
        self.assertIn("keeps forwarding to spectators without a viewer", results[0].failures[0])

    def test_spectator_settings_use_their_own_ports(self):
        orchestrator, _, launcher = self.build_spectator([STATS, STATS])

        orchestrator.run([SPECTATOR_CASES[0]])

        settings = launcher.started_with[1].read_text()
        self.assertIn("spectator_mode = true", settings)
        self.assertIn('id = "spec"', settings)
        self.assertIn("video = 16388", settings)


class TestNegativePath(OrchestratorTestCase):
    def test_expected_failure_line_passes(self):
        orchestrator, _, _ = self.build(
            [],
            [],
            [
                (
                    LogSource.VIDEO,
                    "ERROR - Cannot establish TCP connection to 192.168.1.100:16384 after 30s - is the remote side configured for TCP?",
                )
            ],
        )

        results = orchestrator.run([LOCAL_NEGATIVE_CASES[0]])

        self.assertTrue(results[0].passed)

    def test_unexpected_connection_fails(self):
        orchestrator, _, _ = self.build(["INFO - Control channel connected"], [], [])

        results = orchestrator.run([LOCAL_NEGATIVE_CASES[1]])

        self.assertFalse(results[0].passed)
        self.assertIn("connected although it was expected to fail", results[0].failures[0])

    def test_wrong_id_case_tolerates_stopped_services(self):
        orchestrator, client, _ = self.build(
            ["ERROR - Relay setup failed: Peer registration failed - check server and ID!"],
            [],
            [(LogSource.SERVICE_MANAGER, "ERROR - Unauthorized access - check 'Relay session ID' setting")],
        )
        client.apply_states = {"v3xctrl-video": "inactive", "v3xctrl-control": "inactive"}

        results = orchestrator.run([RELAY_NEGATIVE_CASES[0]])

        self.assertEqual(results[0].failures, [])
        self.assertLess(client.applied_timeouts[0], 90.0)

    def test_case_without_failure_lines_holds_the_connect_timeout(self):
        orchestrator, _, _ = self.build([], [], [])
        started = self.clock()

        results = orchestrator.run([LOCAL_NEGATIVE_CASES[1]])

        self.assertTrue(results[0].passed)
        self.assertGreaterEqual(self.clock() - started, orchestrator.options.connect_timeout)

    def test_late_connection_within_the_hold_fails(self):
        orchestrator, _, _ = self.build([], ["INFO - Control channel connected"], [])

        results = orchestrator.run([LOCAL_NEGATIVE_CASES[1]])

        self.assertFalse(results[0].passed)


class TestRecordStoreTimestamps(unittest.TestCase):
    def test_journal_lines_are_placed_when_journald_stamped_them(self):
        store = RecordStore(clock=lambda: 1000.0, wall_clock=lambda: 1_700_000_000.8)

        store.on_agent_event(
            {"event": "journal", "unit": "v3xctrl-control", "message": "x", "realtime": 1_700_000_000_300_000}
        )

        self.assertAlmostEqual(store.snapshot()[0].captured_at, 999.5, places=3)

    def test_missing_or_implausible_realtime_uses_the_arrival_time(self):
        store = RecordStore(clock=lambda: 1000.0, wall_clock=lambda: 1_700_000_000.0)

        store.on_agent_event({"event": "journal", "unit": "v3xctrl-control", "message": "a"})
        store.on_agent_event(
            {"event": "journal", "unit": "v3xctrl-control", "message": "b", "realtime": 1_699_999_000_000_000}
        )
        store.on_agent_event(
            {"event": "journal", "unit": "v3xctrl-control", "message": "c", "realtime": 1_700_000_005_000_000}
        )

        self.assertEqual([record.captured_at for record in store.snapshot()], [1000.0, 1000.0, 1000.0])


class TestRecordStore(unittest.TestCase):
    def test_journal_events_map_units_to_sources(self):
        store = RecordStore(lambda: 5.0)

        store.on_agent_event({"event": "journal", "unit": "v3xctrl-control", "message": "Connected"})
        store.on_agent_event({"event": "journal", "unit": "sshd", "message": "ignored"})
        store.on_agent_event({"event": "error", "message": "ignored"})

        records = store.snapshot()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0], LogRecord(LogSource.CONTROL, "Connected", 5.0))


class TestInactiveServices(unittest.TestCase):
    def test_all_active_is_clean(self):
        states = {"v3xctrl-video": "active", "v3xctrl-control": "active"}
        self.assertEqual(inactive_services({"states": states}), [])

    def test_inactive_unit_is_named(self):
        states = {"v3xctrl-video": "inactive", "v3xctrl-control": "active"}
        self.assertEqual(
            inactive_services({"states": states}), ["streamer service v3xctrl-video is inactive after apply"]
        )

    def test_missing_states_is_clean(self):
        self.assertEqual(inactive_services({}), [])


class TestBootstrapCheck(unittest.TestCase):
    def check(self, text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.toml"
            path.write_text(text)
            return check_bootstrapped_settings(path)

    def test_empty_file_fails(self):
        self.assertEqual(len(self.check("")), 1)

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            failures = check_bootstrapped_settings(Path(directory) / "settings.toml")

        self.assertEqual(failures, ["bootstrap: the viewer did not create the settings file"])

    def test_unparseable_file_fails(self):
        self.assertIn("does not parse", self.check("= nope")[0])

    def test_missing_sections_are_named(self):
        self.assertIn("lacks", self.check('transport = "udp"\n')[0])

    def test_complete_file_passes(self):
        text = 'transport = "udp"\n[ports]\n[relay]\n[video]\n[widgets]\n[controls]\n[timing]\n'
        self.assertEqual(self.check(text), [])


class TestViewerKindOption(unittest.TestCase):
    def test_default_is_source(self):
        self.assertEqual(options().viewer_kind, ViewerKind.SOURCE)
