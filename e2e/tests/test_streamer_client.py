import json
import queue
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from v3xctrl_e2e.streamer_client import (
    STREAMER_PYTHON,
    AgentError,
    StreamerClient,
    SubprocessTransport,
    ssh_base_command,
)


class FakeTransport:
    """Answers each request from a script keyed by command, and can inject events."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.incoming: queue.Queue[str | None] = queue.Queue()
        self.responses: dict[str, dict] = {}
        self.closed = False

    def send_line(self, line: str) -> None:
        request = json.loads(line)
        self.sent.append(request)
        response = self.responses.get(request["command"])
        if response is not None:
            self.incoming.put(json.dumps({"id": request["id"], **response}))

    def read_line(self) -> str | None:
        return self.incoming.get()

    def close(self) -> None:
        self.closed = True
        self.incoming.put(None)

    def inject(self, payload: dict) -> None:
        self.incoming.put(json.dumps(payload))


class TestStreamerClient(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.events: list[dict] = []
        self.client = StreamerClient(self.transport, self.events.append)
        self.client.start()

    def tearDown(self):
        self.client.close()

    def test_call_returns_the_result(self):
        self.transport.responses["ping"] = {"ok": True, "result": {"hostname": "pi"}}

        self.assertEqual(self.client.ping(), {"hostname": "pi"})
        self.assertEqual(self.transport.sent[0]["command"], "ping")

    def test_error_response_raises(self):
        self.transport.responses["stop_service"] = {"ok": False, "error": "AgentError: refusing"}

        with self.assertRaises(AgentError) as context:
            self.client.stop_service("sshd")

        self.assertIn("refusing", str(context.exception))

    def test_timeout_raises(self):
        with self.assertRaises(AgentError) as context:
            self.client.call("ping", response_timeout=0.05)

        self.assertIn("no response", str(context.exception))

    def test_events_go_to_the_callback(self):
        self.transport.inject({"event": "journal", "unit": "v3xctrl-video", "message": "Building pipeline..."})
        self.transport.responses["ping"] = {"ok": True, "result": {}}

        self.client.ping()

        self.assertEqual(self.events[0]["message"], "Building pipeline...")

    def test_parameters_are_forwarded(self):
        self.transport.responses["begin_case"] = {"ok": True, "result": {"seconds": 3}}

        self.client.begin_case({"viewer": {}}, timeout=40.0)

        request = self.transport.sent[0]
        self.assertEqual(request["config"], {"viewer": {}})
        self.assertEqual(request["timeout"], 40.0)

    def test_closed_connection_fails_pending_calls(self):
        failure: list[Exception] = []

        def caller() -> None:
            try:
                self.client.call("ping", timeout=5.0)
            except AgentError as error:
                failure.append(error)

        thread = threading.Thread(target=caller)
        thread.start()
        self.transport.incoming.put(None)
        thread.join(timeout=2.0)

        self.assertEqual(len(failure), 1)
        self.assertIn("closed", str(failure[0]))


class TestDeployAgent(unittest.TestCase):
    def test_timeout_becomes_an_agent_error(self):
        import subprocess
        from pathlib import Path
        from unittest.mock import patch

        from v3xctrl_e2e.streamer_client import deploy_agent

        with (
            patch("v3xctrl_e2e.streamer_client.subprocess.run", side_effect=subprocess.TimeoutExpired("ssh", 60)),
            self.assertRaises(AgentError) as context,
        ):
            deploy_agent("chris", "192.168.1.225", Path("/tmp/e2e.sock"))

        self.assertIn("longer than 60s", str(context.exception))


class TestSshCommand(unittest.TestCase):
    def test_uses_one_multiplexed_key_only_connection(self):
        from pathlib import Path

        command = ssh_base_command("chris", "192.168.1.225", Path("/tmp/e2e.sock"))

        self.assertEqual(command[0], "ssh")
        self.assertIn("PreferredAuthentications=publickey", command)
        self.assertIn("ControlMaster=auto", command)
        self.assertIn("ControlPath=/tmp/e2e.sock", command)
        self.assertEqual(command[-1], "chris@192.168.1.225")


class TestAgentInterpreter(unittest.TestCase):
    def test_agent_runs_under_the_streamer_python(self):
        with patch("v3xctrl_e2e.streamer_client.subprocess.Popen") as popen:
            popen.return_value.stdin = None
            popen.return_value.stdout = None
            SubprocessTransport.open_ssh("chris", "192.168.1.138", Path("/tmp/x.sock"), "/tmp/agent.py")

        command = popen.call_args[0][0]
        self.assertEqual(command[-1], f"{STREAMER_PYTHON} -u /tmp/agent.py")
        self.assertEqual(STREAMER_PYTHON, "/opt/v3xctrl-venv/bin/python")
