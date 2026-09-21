#!/usr/bin/env python3
"""Streamer-side agent for the v3xctrl end-to-end harness.

Copied to the streamer by the orchestrator and run over one SSH session. It
reads one JSON request per line on stdin and writes one JSON line per
response on stdout. Journal lines are streamed as events on the same stream.

The commands follow the harness's shape, a run holding test cases:
`open_run` snapshots the live config, `begin_case` follows the journal from
before the restart and applies a config, `end_case` stops following,
`close_run` restores the snapshot. The order that keeps journal lines from
being lost is kept in here.

Runs under the streamer's own interpreter, /opt/v3xctrl-venv/bin/python
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

CONFIG_PATH = "/data/config/config.json"
SNAPSHOT_PATH = "/tmp/v3xctrl_e2e_config_snapshot.json"
WRITE_ENV_PATH = "/usr/bin/v3xctrl-write-env"
SERVICE_MANAGER_UNIT = "v3xctrl-service-manager"
STREAM_UNITS = ("v3xctrl-video", "v3xctrl-control")
JOURNAL_UNITS = (SERVICE_MANAGER_UNIT, "v3xctrl-video", "v3xctrl-control")
ALLOWED_SERVICE_UNITS = frozenset(STREAM_UNITS)

DEFAULT_APPLY_TIMEOUT_SECONDS = 90.0
COMMAND_TIMEOUT_SECONDS = 120


class AgentError(Exception):
    pass


def run_command(
    arguments: list[str], input_text: str | None = None, timeout: float = COMMAND_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, input=input_text, capture_output=True, text=True, timeout=timeout, check=False)


def sudo(*arguments: str) -> list[str]:
    return ["sudo", "-n", *arguments]


def parse_cursor(text: str) -> str | None:
    """journalctl --show-cursor prints `-- cursor: s=...` as its last line."""
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("-- cursor:"):
            return stripped[len("-- cursor:") :].strip()

    return None


def parse_journal_entry(line: str) -> dict[str, Any] | None:
    """One `journalctl -o json` line to the fields the orchestrator needs."""
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return None

    message = entry.get("MESSAGE")
    if not isinstance(message, str):
        return None

    unit = entry.get("_SYSTEMD_UNIT") or entry.get("UNIT") or ""
    if isinstance(unit, str) and unit.endswith(".service"):
        unit = unit[: -len(".service")]

    return {
        "event": "journal",
        "unit": unit,
        "message": message,
        "cursor": entry.get("__CURSOR", ""),
        "realtime": int(entry.get("__REALTIME_TIMESTAMP", 0) or 0),
    }


def autostarted_units(config: dict[str, Any]) -> tuple[str, ...]:
    """The stream units the service manager starts for this config."""
    units: list[str] = []
    if config.get("video", {}).get("autostart"):
        units.append("v3xctrl-video")

    if config.get("control", {}).get("autostart"):
        units.append("v3xctrl-control")

    return tuple(units)


def is_within_directory(path: str, directory: str) -> bool:
    real_path = os.path.realpath(path)
    real_directory = os.path.realpath(directory)
    return real_path.startswith(real_directory.rstrip("/") + "/")


class Output:
    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._lock = threading.Lock()

    def emit(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._stream.write(json.dumps(payload) + "\n")
            self._stream.flush()


class JournalFollower(threading.Thread):
    def __init__(self, cursor: str | None, output: Output) -> None:
        super().__init__(name="journal-follower", daemon=True)
        self._cursor = cursor
        self._output = output
        self._process: subprocess.Popen[str] | None = None

    def run(self) -> None:
        arguments = ["journalctl", "-f", "-o", "json", "-q", "--no-tail"]
        if self._cursor:
            arguments.extend(["--after-cursor", self._cursor])
        else:
            arguments.extend(["--since", "now"])
        for unit in JOURNAL_UNITS:
            arguments.extend(["-u", unit])

        self._process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        assert self._process.stdout is not None
        for line in self._process.stdout:
            entry = parse_journal_entry(line)
            if entry is not None:
                self._output.emit(entry)

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

        self.join(timeout=5)


class Agent:
    def __init__(self, output: Output) -> None:
        self._output = output
        self._follower: JournalFollower | None = None
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "ping": self.ping,
            "open_run": self.open_run,
            "begin_case": self.begin_case,
            "end_case": self.end_case,
            "close_run": self.close_run,
            "stop_service": self.stop_service,
            "start_service": self.start_service,
            "delete_recording": self.delete_recording,
        }

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        command = request.get("command")
        handler = self._handlers.get(str(command))
        if handler is None:
            raise AgentError(f"unknown command: {command}")

        return handler(request)

    def ping(self, request: dict[str, Any]) -> dict[str, Any]:
        """Who the streamer is and how busy it is, for preflight."""
        completed = run_command(["dpkg-query", "-W", "-f", "${Version}", "v3xctrl"])
        one, five, fifteen = os.getloadavg()
        return {
            "hostname": socket.gethostname(),
            "package_version": completed.stdout.strip() if completed.returncode == 0 else None,
            "python_version": sys.version.split()[0],
            "load_average": [one, five, fifteen],
            "cpu_count": os.cpu_count() or 1,
        }

    def _stop_stream_units(self) -> None:
        completed = run_command(sudo("systemctl", "stop", *STREAM_UNITS))
        if completed.returncode != 0:
            raise AgentError(f"systemctl stop failed: {completed.stderr.strip()}")

    def open_run(self, request: dict[str, Any]) -> dict[str, Any]:
        """Snapshot the live config so `close_run` can put it back, and hand it over.

        A snapshot left behind by a run that was killed before `close_run` is
        the operator's config; it is kept and handed over in place of the live
        one, which is that run's last test config.

        The stream units are stopped as well: the first case's viewer starts
        before its config is applied, and an autostarted control service from
        before the run would answer it and then be restarted under it.
        """
        if os.path.exists(SNAPSHOT_PATH):
            with open(SNAPSHOT_PATH, encoding="utf-8") as handle:
                text = handle.read()
            reused = True
        else:
            text = self._read_config_text()
            with open(SNAPSHOT_PATH, "w", encoding="utf-8") as handle:
                handle.write(text)
            reused = False

        self._stop_stream_units()
        return {"config": json.loads(text), "snapshot": SNAPSHOT_PATH, "reused": reused}

    def begin_case(self, request: dict[str, Any]) -> dict[str, Any]:
        """Follow the journal from before the restart, then write and apply the config.

        The cursor is taken before anything changes so the service start lines
        land in the timeline; a failed apply leaves the follower running so its
        journal lines are captured too, `end_case` stops it either way.
        """
        self._stop_follower()
        cursor = self._journal_cursor()
        self._follower = JournalFollower(cursor, self._output)
        self._follower.start()

        self._write_config_text(json.dumps(request["config"], indent=2) + "\n")
        timeout = float(request.get("timeout", DEFAULT_APPLY_TIMEOUT_SECONDS))
        result = self._apply_live_config(timeout, autostarted_units(request["config"]))
        result["cursor"] = cursor
        return result

    def end_case(self, request: dict[str, Any]) -> dict[str, Any]:
        """Stop following the journal, then stop the stream units.

        The next case starts its viewer before its config is applied, and with
        the units stopped that viewer can only reach the services the apply
        starts. The stop runs after the follower so its lines stay out of the
        case's timeline.
        """
        self._stop_follower()
        self._stop_stream_units()

        return {"states": self._service_states()}

    def _stop_follower(self) -> None:
        if self._follower is not None:
            self._follower.stop()
            self._follower = None

    def close_run(self, request: dict[str, Any]) -> dict[str, Any]:
        """Put the snapshot back and restart on it. Safe to call without an open run."""
        self._stop_follower()
        if not os.path.exists(SNAPSHOT_PATH):
            raise AgentError("no snapshot to restore")

        with open(SNAPSHOT_PATH, encoding="utf-8") as handle:
            text = handle.read()
        self._write_config_text(text)

        timeout = float(request.get("timeout", DEFAULT_APPLY_TIMEOUT_SECONDS))
        result = self._apply_live_config(timeout, autostarted_units(json.loads(text)))
        os.remove(SNAPSHOT_PATH)
        return result

    def stop_service(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._control_service("stop", str(request["unit"]))

    def start_service(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._control_service("start", str(request["unit"]))

    def _journal_cursor(self) -> str | None:
        completed = run_command(["journalctl", "-n", "0", "-q", "--show-cursor"])
        return parse_cursor(completed.stdout)

    def delete_recording(self, request: dict[str, Any]) -> dict[str, Any]:
        path = str(request["path"])
        config = json.loads(self._read_config_text())
        directory = config.get("video", {}).get("record", {}).get("path", "/data/recordings")
        if not is_within_directory(path, directory):
            raise AgentError(f"refusing to delete {path}: outside {directory}")

        completed = run_command(sudo("rm", "-f", path))
        if completed.returncode != 0:
            raise AgentError(completed.stderr.strip())

        return {}

    def _read_config_text(self) -> str:
        completed = run_command(sudo("cat", CONFIG_PATH))
        if completed.returncode != 0:
            raise AgentError(f"cannot read {CONFIG_PATH}: {completed.stderr.strip()}")

        return completed.stdout

    def _write_config_text(self, text: str) -> None:
        json.loads(text)
        completed = run_command(sudo("tee", CONFIG_PATH), input_text=text)
        if completed.returncode != 0:
            raise AgentError(f"cannot write {CONFIG_PATH}: {completed.stderr.strip()}")

        run_command(["sync"])

    def _apply_live_config(self, timeout: float, expected_units: tuple[str, ...]) -> dict[str, Any]:
        """Restart on the written config and wait for the units it autostarts."""
        started = time.monotonic()
        write_env = run_command(sudo(WRITE_ENV_PATH))
        if write_env.returncode != 0:
            raise AgentError(f"write-env failed: {write_env.stderr.strip()}")

        restart = run_command(sudo("systemctl", "restart", SERVICE_MANAGER_UNIT), timeout=timeout)
        states = self._wait_active(timeout - (time.monotonic() - started), expected_units)
        return {
            "restart_returncode": restart.returncode,
            "restart_stderr": restart.stderr.strip(),
            "states": states,
            "seconds": round(time.monotonic() - started, 1),
        }

    def _wait_active(self, timeout: float, expected_units: tuple[str, ...]) -> dict[str, str]:
        deadline = time.monotonic() + max(timeout, 0.0)
        states = self._service_states()
        while time.monotonic() < deadline and any(states[unit] != "active" for unit in expected_units):
            time.sleep(1.0)
            states = self._service_states()

        return states

    def _service_states(self) -> dict[str, str]:
        completed = run_command(["systemctl", "is-active", *STREAM_UNITS])
        lines = completed.stdout.split()
        return {unit: (lines[index] if index < len(lines) else "unknown") for index, unit in enumerate(STREAM_UNITS)}

    def _control_service(self, action: str, unit: str) -> dict[str, Any]:
        if unit not in ALLOWED_SERVICE_UNITS:
            raise AgentError(f"refusing to {action} {unit}")

        completed = run_command(sudo("systemctl", action, unit))
        if completed.returncode != 0:
            raise AgentError(f"systemctl {action} {unit} failed: {completed.stderr.strip()}")

        return {"states": self._service_states()}

    def shutdown(self) -> None:
        self._stop_follower()


def serve(input_stream: Any, output_stream: Any) -> None:
    output = Output(output_stream)
    agent = Agent(output)
    try:
        for line in input_stream:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError as error:
                output.emit({"event": "error", "message": f"malformed request: {error}"})
                continue

            request_id = request.get("id")
            try:
                result = agent.handle(request)
                output.emit({"id": request_id, "ok": True, "result": result})
            except Exception as error:
                output.emit({"id": request_id, "ok": False, "error": f"{type(error).__name__}: {error}"})
    finally:
        agent.shutdown()


if __name__ == "__main__":
    serve(sys.stdin, sys.stdout)
