"""Command line entry point."""

import argparse
import logging
import os
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from v3xctrl_e2e.artifacts import DEFAULT_RUNS_DIRECTORY, RunDirectory, format_summary_table, write_summary
from v3xctrl_e2e.matrix import Phase, build_matrix, needs_streamer, uses_relay
from v3xctrl_e2e.orchestrator import Orchestrator, RunOptions
from v3xctrl_e2e.preflight import (
    check_agent,
    check_display,
    check_gstreamer,
    check_load,
    check_local_ports,
    check_relay,
    check_uinput,
    check_viewer_flags,
    has_viewer_titles,
    split_relay_host,
)
from v3xctrl_e2e.streamer_client import (
    AgentError,
    StreamerClient,
    SubprocessTransport,
    close_control_master,
    deploy_agent,
)
from v3xctrl_e2e.viewer_config import GamepadBinding
from v3xctrl_e2e.viewer_launcher import ViewerKind, ViewerLauncher
from v3xctrl_e2e.virtual_gamepad import VirtualGamepad, binding_for, discover_guid

SOURCE_DIRECTORY = Path(__file__).resolve().parents[2] / "src"

EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_PREFLIGHT = 2

# Two full 10 s receiver stats windows, the first one is skipped as partial.
MINIMUM_STEADY_SECONDS = 20.0


def parse_arguments(argv: list[str]) -> RunOptions:
    parser = argparse.ArgumentParser(prog="v3xctrl_e2e", description="End-to-end test run against a real streamer.")
    parser.add_argument("--streamer-host", default=None, help="LAN address of the streamer (local and relay phases)")
    parser.add_argument("--ssh-user", default=None, help="SSH user on the streamer, with passwordless sudo")
    parser.add_argument("--relay-id", default="", help="Relay session ID (viewer and relay phases)")
    parser.add_argument("--relay-host", default="relay.v3xctrl.com:8888", help="Relay host:port")
    parser.add_argument(
        "--only",
        action="append",
        choices=[phase.value for phase in Phase],
        help="Run only this phase; repeat the flag for several phases",
    )
    parser.add_argument("--negative", action="store_true", help="Include the negative tests")
    parser.add_argument("--case", action="append", default=[], help="Run only this case by name; repeatable")
    parser.add_argument(
        "--spectator-id", default="", help="Spectator ID for the relay session; adds the spectator soak cases"
    )
    parser.add_argument(
        "--spectator-seconds",
        type=float,
        default=60.0,
        help="How long viewer and spectator are held together; the relay drops a spectator after 30 s of silence",
    )
    parser.add_argument("--viewer", choices=[kind.value for kind in ViewerKind], default=ViewerKind.SOURCE.value)
    parser.add_argument("--viewer-python", default=sys.executable, help="Interpreter for the source viewer")
    parser.add_argument(
        "--viewer-source",
        type=Path,
        default=SOURCE_DIRECTORY,
        help="src directory of the viewer checkout under test (default: this repository)",
    )
    parser.add_argument("--headless", action="store_true", help="Run the viewer under the SDL dummy video driver")
    parser.add_argument("--camera", action="store_true", help="Stream from the camera instead of the test source")
    parser.add_argument(
        "--without-gamepad", action="store_true", help="Skip the virtual gamepad and the input scenario"
    )
    parser.add_argument("--steady-seconds", type=float, default=20.0)
    parser.add_argument("--connect-timeout", type=float, default=45.0)
    parser.add_argument("--apply-timeout", type=float, default=90.0)
    parser.add_argument("--min-fps", type=int, default=None, help="Default: source frame rate minus 5")
    parser.add_argument(
        "--max-drop-rate",
        type=float,
        default=10.0,
        help="Percent of frames the viewer may skip per stats window to keep latency down",
    )
    parser.add_argument("--telemetry-tolerance", type=float, default=0.2, help="Fraction below the expected rate")
    parser.add_argument("--max-load-per-cpu", type=float, default=0.75)
    parser.add_argument("--runs-directory", type=Path, default=DEFAULT_RUNS_DIRECTORY)
    parser.add_argument("--verbose", action="store_true")

    arguments = parser.parse_args(argv)

    phases = {Phase(value) for value in arguments.only} if arguments.only else set(Phase)
    if Phase.RELAY in phases and not arguments.relay_id:
        parser.error("--relay-id is required for the relay phase")

    if arguments.steady_seconds < MINIMUM_STEADY_SECONDS:
        parser.error(
            f"--steady-seconds must be at least {MINIMUM_STEADY_SECONDS:.0f}: the viewer reports receiver stats "
            f"and telemetry counts every 10 s and the first stats line is skipped"
        )

    if needs_streamer(phases) and not (arguments.streamer_host and arguments.ssh_user):
        parser.error("--streamer-host and --ssh-user are required for the local and relay phases")

    logging.basicConfig(
        level=logging.DEBUG if arguments.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    return RunOptions(
        streamer_host=arguments.streamer_host,
        ssh_user=arguments.ssh_user,
        relay_host=arguments.relay_host,
        relay_id=arguments.relay_id,
        phases=phases,
        include_negative=arguments.negative,
        viewer_kind=ViewerKind(arguments.viewer),
        viewer_python=arguments.viewer_python,
        headless=arguments.headless,
        use_camera=arguments.camera,
        spectator_id=arguments.spectator_id,
        case_names=list(arguments.case),
        spectator_seconds=arguments.spectator_seconds,
        with_gamepad=not arguments.without_gamepad,
        steady_seconds=arguments.steady_seconds,
        connect_timeout=arguments.connect_timeout,
        apply_timeout=arguments.apply_timeout,
        minimum_fps=arguments.min_fps,
        maximum_drop_rate=arguments.max_drop_rate,
        telemetry_tolerance=arguments.telemetry_tolerance,
        maximum_load_per_cpu=arguments.max_load_per_cpu,
        runs_directory=arguments.runs_directory,
        viewer_source=arguments.viewer_source,
    )


def run_preflight(
    options: RunOptions, client: StreamerClient | None, with_relay: bool, launcher: ViewerLauncher | None = None
) -> list[str]:
    failures: list[str] = []
    if client is not None:
        failures = check_agent(client.ping)
        if failures:
            return failures
        failures.extend(check_load(client.ping(), options.maximum_load_per_cpu))

    failures.extend(check_local_ports([options.video_port, options.control_port]))
    failures.extend(check_display(options.headless))
    if options.viewer_kind == ViewerKind.SOURCE:
        failures.extend(check_gstreamer())

    if launcher is not None:
        try:
            help_text = launcher.help_text()
            failures.extend(check_viewer_flags(help_text))
            launcher.supports_title = has_viewer_titles(help_text)
            if not launcher.supports_title:
                logging.warning("viewer under test has no --title flag; its windows stay untitled")
        except (OSError, subprocess.TimeoutExpired) as error:
            failures.append(f"viewer under test cannot be started: {error}")

    if options.with_gamepad and needs_streamer(options.phases):
        failures.extend(check_uinput())

    if with_relay:
        host, port = split_relay_host(options.relay_host)
        failures.extend(check_relay(host, port, options.relay_id))

    return failures


def _interrupt_on_terminate(signal_number: int, frame: Any) -> None:
    """SIGTERM unwinds like Ctrl-C so the viewers stop and the streamer config is restored."""
    raise KeyboardInterrupt


def skipped_case_groups(options: RunOptions) -> list[str]:
    """The case groups a run leaves out for want of a flag, for the start-of-run notice."""
    if options.case_names:
        return []

    skipped: list[str] = []
    if not options.include_negative:
        skipped.append("the negative cases (add --negative)")

    if Phase.RELAY in options.phases and options.relay_id and not options.spectator_id:
        skipped.append("the spectator cases (add --spectator-id)")

    return skipped


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGTERM, _interrupt_on_terminate)
    options = parse_arguments(sys.argv[1:] if argv is None else argv)
    run_directory = RunDirectory(options.runs_directory)
    control_path = Path(f"/tmp/v3xctrl-e2e-{os.getpid()}.sock")

    try:
        return run(options, run_directory, control_path)

    except AgentError as error:
        logging.error(f"preflight: {error}")
        return EXIT_PREFLIGHT

    finally:
        if options.streamer_host and options.ssh_user:
            close_control_master(options.ssh_user, options.streamer_host, control_path)


def connect_streamer(
    options: RunOptions, control_path: Path, on_event: Callable[[dict[str, Any]], None]
) -> StreamerClient:
    assert options.ssh_user is not None and options.streamer_host is not None
    remote_agent = deploy_agent(options.ssh_user, options.streamer_host, control_path)
    transport = SubprocessTransport.open_ssh(options.ssh_user, options.streamer_host, control_path, remote_agent)

    client = StreamerClient(transport, on_event)
    client.start()
    return client


def run(options: RunOptions, run_directory: RunDirectory, control_path: Path) -> int:
    source_directory = options.viewer_source or SOURCE_DIRECTORY
    launcher = ViewerLauncher(options.viewer_kind, options.viewer_python, source_directory, options.headless)
    gamepad: VirtualGamepad | None = None
    binding: GamepadBinding | None = None
    orchestrator: Orchestrator | None = None

    def on_event(event: dict[str, Any]) -> None:
        if orchestrator is not None:
            orchestrator.on_agent_event(event)

    cases = build_matrix(
        options.phases,
        options.include_negative,
        with_relay=bool(options.relay_id),
        with_spectator=bool(options.spectator_id),
    )
    if options.case_names:
        unknown = sorted(set(options.case_names) - {case.name for case in cases})
        if unknown:
            logging.error(f"unknown case names: {', '.join(unknown)}")
            return EXIT_PREFLIGHT

        cases = [case for case in cases if case.name in options.case_names]

    if not options.relay_id and uses_relay(build_matrix(options.phases, options.include_negative)):
        logging.warning("no --relay-id given: the viewer phase runs without its relay cases")

    skipped = skipped_case_groups(options)
    if skipped:
        logging.info(f"running {len(cases)} cases, skipping {' and '.join(skipped)}")

    client = connect_streamer(options, control_path, on_event) if needs_streamer(options.phases) else None

    try:
        failures = run_preflight(options, client, with_relay=uses_relay(cases), launcher=launcher)
        if failures:
            for failure in failures:
                logging.error(f"preflight: {failure}")
            return EXIT_PREFLIGHT

        if options.with_gamepad and needs_streamer(options.phases):
            gamepad = VirtualGamepad()
            gamepad.open()
            binding = binding_for(discover_guid(options.viewer_python))
            logging.info(f"virtual gamepad ready, GUID {binding.guid}")

        orchestrator = Orchestrator(options, client, launcher, run_directory, gamepad, binding)
        results = orchestrator.run(cases)

        write_summary(run_directory, results, {"options": {**vars(options), "phases": sorted(options.phases)}})
        print(format_summary_table(results))
        print(f"\nartifacts: {run_directory.path}")
        return EXIT_PASSED if all(result.passed for result in results) else EXIT_FAILED

    finally:
        if gamepad is not None:
            gamepad.close()

        if client is not None:
            client.close()
