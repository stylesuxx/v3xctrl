"""Orchestrator-side client for the streamer agent."""

import json
import logging
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

AGENT_SOURCE = Path(__file__).resolve().parents[1] / "agent" / "streamer_agent.py"
REMOTE_AGENT_PATH = "/tmp/v3xctrl_e2e_agent.py"

# The streamer image ships its own interpreter with the v3xctrl packages installed.
STREAMER_PYTHON = "/opt/v3xctrl-venv/bin/python"
DEFAULT_CALL_TIMEOUT_SECONDS = 30.0
DEPLOY_TIMEOUT_SECONDS = 60


class AgentError(Exception):
    pass


class AgentTransport(Protocol):
    def send_line(self, line: str) -> None: ...

    def read_line(self) -> str | None: ...

    def close(self) -> None: ...


def ssh_base_command(user: str, host: str, control_path: Path) -> list[str]:
    """One multiplexed connection for the run; the first call opens it, the rest reuse it."""
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "PreferredAuthentications=publickey",
        "-o",
        "ConnectTimeout=15",
        "-o",
        "ControlMaster=auto",
        "-o",
        f"ControlPath={control_path}",
        "-o",
        "ControlPersist=600",
        f"{user}@{host}",
    ]


def deploy_agent(user: str, host: str, control_path: Path, agent_source: Path = AGENT_SOURCE) -> str:
    try:
        with agent_source.open("rb") as handle:
            completed = subprocess.run(
                [*ssh_base_command(user, host, control_path), f"cat > {REMOTE_AGENT_PATH}"],
                stdin=handle,
                capture_output=True,
                timeout=DEPLOY_TIMEOUT_SECONDS,
                check=False,
            )

    except subprocess.TimeoutExpired as error:
        raise AgentError(
            f"copying the agent to {host} took longer than {DEPLOY_TIMEOUT_SECONDS}s; "
            "is the streamer reachable and idle?"
        ) from error

    if completed.returncode != 0:
        raise AgentError(f"could not copy the agent to {host}: {completed.stderr.decode().strip()}")

    return REMOTE_AGENT_PATH


def close_control_master(user: str, host: str, control_path: Path) -> None:
    subprocess.run([*ssh_base_command(user, host, control_path), "-O", "exit"], capture_output=True, check=False)


class SubprocessTransport:
    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process

    @classmethod
    def open_ssh(cls, user: str, host: str, control_path: Path, remote_agent_path: str) -> "SubprocessTransport":
        process = subprocess.Popen(
            [*ssh_base_command(user, host, control_path), f"{STREAMER_PYTHON} -u {remote_agent_path}"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        return cls(process)

    def send_line(self, line: str) -> None:
        assert self._process.stdin is not None
        self._process.stdin.write(line + "\n")
        self._process.stdin.flush()

    def read_line(self) -> str | None:
        assert self._process.stdout is not None
        line = self._process.stdout.readline()
        return line if line else None

    def close(self) -> None:
        if self._process.stdin is not None:
            self._process.stdin.close()

        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.kill()


class _PendingCall:
    def __init__(self) -> None:
        self.done = threading.Event()
        self.response: dict[str, Any] | None = None


class StreamerClient:
    """Sends commands, matches responses by id, hands events to `on_event`."""

    def __init__(self, transport: AgentTransport, on_event: Callable[[dict[str, Any]], None]) -> None:
        self._transport = transport
        self._on_event = on_event
        self._pending: dict[int, _PendingCall] = {}
        self._lock = threading.Lock()
        self._next_id = 1
        self._closed = threading.Event()
        self._reader = threading.Thread(target=self._pump, name="agent-reader", daemon=True)

    def start(self) -> None:
        self._reader.start()

    def close(self) -> None:
        self._closed.set()
        self._transport.close()
        self._reader.join(timeout=5.0)

    def call(
        self, command: str, response_timeout: float = DEFAULT_CALL_TIMEOUT_SECONDS, **parameters: Any
    ) -> dict[str, Any]:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            pending = _PendingCall()
            self._pending[request_id] = pending

        self._transport.send_line(json.dumps({"id": request_id, "command": command, **parameters}))

        if not pending.done.wait(response_timeout):
            with self._lock:
                self._pending.pop(request_id, None)

            raise AgentError(f"{command}: no response within {response_timeout}s")

        response = pending.response or {}
        if not response.get("ok"):
            raise AgentError(f"{command}: {response.get('error', 'unknown error')}")

        result: dict[str, Any] = response.get("result", {})
        return result

    def _pump(self) -> None:
        while not self._closed.is_set():
            line = self._transport.read_line()
            if line is None:
                break

            line = line.strip()
            if not line:
                continue

            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue

            if "event" in message:
                self._on_event(message)
                continue

            with self._lock:
                pending = self._pending.pop(int(message.get("id", -1)), None)

            if pending is not None:
                pending.response = message
                pending.done.set()

        self._fail_pending("agent connection closed")

    def _fail_pending(self, reason: str) -> None:
        with self._lock:
            pending_calls = list(self._pending.values())
            self._pending.clear()

        for pending in pending_calls:
            pending.response = {"ok": False, "error": reason}
            pending.done.set()

    def ping(self) -> dict[str, Any]:
        return self.call("ping")

    def open_run(self) -> dict[str, Any]:
        """The streamer's live config; the agent keeps a snapshot for `close_run`."""
        result = self.call("open_run")
        if result.get("reused"):
            logger.warning("the previous run ended without restoring the streamer config; its snapshot is used")
        config: dict[str, Any] = result["config"]
        return config

    def begin_case(self, config: dict[str, Any], timeout: float) -> dict[str, Any]:
        """Journal events start flowing before the config is applied."""
        return self.call("begin_case", response_timeout=timeout + 30.0, config=config, timeout=timeout)

    def end_case(self) -> None:
        self.call("end_case")

    def close_run(self, timeout: float) -> dict[str, Any]:
        return self.call("close_run", response_timeout=timeout + 30.0, timeout=timeout)

    def stop_service(self, unit: str) -> dict[str, Any]:
        return self.call("stop_service", unit=unit)

    def start_service(self, unit: str) -> dict[str, Any]:
        return self.call("start_service", unit=unit)

    def delete_recording(self, path: str) -> None:
        self.call("delete_recording", path=path)
