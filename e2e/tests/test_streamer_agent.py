import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import streamer_agent


def completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestParsers(unittest.TestCase):
    def test_cursor_is_read_from_the_last_line(self):
        text = "-- No entries --\n-- cursor: s=abc;i=1\n"

        self.assertEqual(streamer_agent.parse_cursor(text), "s=abc;i=1")

    def test_missing_cursor(self):
        self.assertIsNone(streamer_agent.parse_cursor(""))

    def test_journal_entry_strips_the_unit_suffix(self):
        line = json.dumps(
            {
                "_SYSTEMD_UNIT": "v3xctrl-video.service",
                "MESSAGE": "Building pipeline...",
                "__CURSOR": "s=1",
                "__REALTIME_TIMESTAMP": "1700000000000000",
            }
        )

        entry = streamer_agent.parse_journal_entry(line)

        assert entry is not None
        self.assertEqual(entry["unit"], "v3xctrl-video")
        self.assertEqual(entry["message"], "Building pipeline...")
        self.assertEqual(entry["realtime"], 1700000000000000)

    def test_systemd_own_lines_use_the_unit_field(self):
        line = json.dumps({"UNIT": "v3xctrl-control.service", "MESSAGE": "Stopped Control channel."})

        entry = streamer_agent.parse_journal_entry(line)

        assert entry is not None
        self.assertEqual(entry["unit"], "v3xctrl-control")

    def test_binary_messages_and_garbage_are_skipped(self):
        self.assertIsNone(streamer_agent.parse_journal_entry(json.dumps({"MESSAGE": [1, 2, 3]})))
        self.assertIsNone(streamer_agent.parse_journal_entry("not json"))

    def test_autostarted_units_follow_the_config(self):
        both = {"video": {"autostart": True}, "control": {"autostart": True}}
        control_only = {"video": {"autostart": False}, "control": {"autostart": True}}

        self.assertEqual(streamer_agent.autostarted_units(both), ("v3xctrl-video", "v3xctrl-control"))
        self.assertEqual(streamer_agent.autostarted_units(control_only), ("v3xctrl-control",))
        self.assertEqual(streamer_agent.autostarted_units({}), ())

    def test_is_within_directory(self):
        self.assertTrue(streamer_agent.is_within_directory("/data/recordings/a.ts", "/data/recordings"))
        self.assertFalse(
            streamer_agent.is_within_directory("/data/recordings/../config/config.json", "/data/recordings")
        )
        self.assertFalse(streamer_agent.is_within_directory("/data/recordings", "/data/recordings"))


class TestServe(unittest.TestCase):
    def serve(self, requests: list[dict], run_command) -> list[dict]:
        input_stream = io.StringIO("".join(json.dumps(request) + "\n" for request in requests))
        output_stream = io.StringIO()
        with patch.object(streamer_agent, "run_command", side_effect=run_command):
            streamer_agent.serve(input_stream, output_stream)
        return [json.loads(line) for line in output_stream.getvalue().splitlines()]

    def test_ping(self):
        def run_command(arguments, input_text=None, timeout=0):
            return completed("1.0.0")

        responses = self.serve([{"id": 1, "command": "ping"}], run_command)

        self.assertTrue(responses[0]["ok"])
        self.assertEqual(responses[0]["result"]["package_version"], "1.0.0")

    def test_unknown_command_is_an_error_response(self):
        responses = self.serve([{"id": 7, "command": "reboot"}], lambda *a, **k: completed())

        self.assertEqual(responses[0]["id"], 7)
        self.assertFalse(responses[0]["ok"])
        self.assertIn("unknown command", responses[0]["error"])

    def test_malformed_line_is_reported_as_an_event(self):
        input_stream = io.StringIO("{not json\n")
        output_stream = io.StringIO()

        streamer_agent.serve(input_stream, output_stream)

        event = json.loads(output_stream.getvalue())
        self.assertEqual(event["event"], "error")

    def test_service_control_is_limited_to_the_stream_units(self):
        calls: list[list[str]] = []

        def run_command(arguments, input_text=None, timeout=0):
            calls.append(arguments)
            return completed("active\nactive\n")

        responses = self.serve(
            [
                {"id": 1, "command": "stop_service", "unit": "sshd"},
                {"id": 2, "command": "stop_service", "unit": "v3xctrl-video"},
            ],
            run_command,
        )

        self.assertFalse(responses[0]["ok"])
        self.assertTrue(responses[1]["ok"])
        self.assertIn(["sudo", "-n", "systemctl", "stop", "v3xctrl-video"], calls)

    def test_begin_case_takes_the_cursor_before_touching_the_streamer(self):
        calls: list[tuple[list[str], str | None]] = []

        def run_command(arguments, input_text=None, timeout=0):
            calls.append((arguments, input_text))
            if arguments[:2] == ["systemctl", "is-active"]:
                return completed("active\nactive\n")
            if arguments[:2] == ["journalctl", "-n"]:
                return completed("-- cursor: s=abc\n")
            return completed()

        with patch.object(streamer_agent, "JournalFollower") as follower:
            responses = self.serve(
                [{"id": 1, "command": "begin_case", "config": {"viewer": {"mode": "direct"}}, "timeout": 5}],
                run_command,
            )

        self.assertTrue(responses[0]["ok"])
        result = responses[0]["result"]
        self.assertEqual(result["states"], {"v3xctrl-video": "active", "v3xctrl-control": "active"})
        self.assertEqual(result["cursor"], "s=abc")
        follower.assert_called_once()
        self.assertEqual(follower.call_args[0][0], "s=abc")

        commands = [arguments for arguments, _ in calls]
        self.assertEqual(commands[0], ["journalctl", "-n", "0", "-q", "--show-cursor"])
        self.assertEqual(commands[1], ["sudo", "-n", "tee", streamer_agent.CONFIG_PATH])
        self.assertEqual(json.loads(calls[1][1] or ""), {"viewer": {"mode": "direct"}})
        self.assertEqual(commands[3], ["sudo", "-n", streamer_agent.WRITE_ENV_PATH])
        self.assertEqual(commands[4], ["sudo", "-n", "systemctl", "restart", "v3xctrl-service-manager"])

    def test_end_case_stops_the_stream_units_after_the_follower(self):
        events: list[str] = []

        def run_command(arguments, input_text=None, timeout=0):
            events.append(" ".join(arguments))
            if arguments[:2] == ["systemctl", "is-active"]:
                return completed("inactive\ninactive\n")
            return completed()

        with patch.object(streamer_agent, "JournalFollower") as follower:
            follower.return_value.stop.side_effect = lambda: events.append("follower stopped")
            responses = self.serve(
                [
                    {"id": 1, "command": "begin_case", "config": {}, "timeout": 5},
                    {"id": 2, "command": "end_case"},
                ],
                run_command,
            )

        self.assertTrue(responses[1]["ok"])
        self.assertEqual(responses[1]["result"]["states"], {"v3xctrl-video": "inactive", "v3xctrl-control": "inactive"})
        stop_index = events.index("sudo -n systemctl stop v3xctrl-video v3xctrl-control")
        self.assertEqual(events[stop_index - 1], "follower stopped")

    def test_open_run_snapshots_the_live_config_and_close_run_restores_it(self):
        calls: list[tuple[list[str], str | None]] = []
        live = '{"viewer": {"mode": "relay"}, "video": {"autostart": false}, "control": {"autostart": true}}'

        def run_command(arguments, input_text=None, timeout=0):
            calls.append((arguments, input_text))
            if arguments == ["sudo", "-n", "cat", streamer_agent.CONFIG_PATH]:
                return completed(live)
            if arguments[:2] == ["systemctl", "is-active"]:
                # Video stays inactive on this config; the restore must not wait for it.
                return completed("inactive\nactive\n")
            return completed()

        with tempfile.TemporaryDirectory() as directory:
            snapshot = f"{directory}/snapshot.json"
            with (
                patch.object(streamer_agent, "SNAPSHOT_PATH", snapshot),
                patch.object(streamer_agent.time, "sleep", side_effect=AssertionError("waited for a unit")),
            ):
                responses = self.serve(
                    [{"id": 1, "command": "open_run"}, {"id": 2, "command": "close_run", "timeout": 5}], run_command
                )
                self.assertFalse(os.path.exists(snapshot))

        self.assertEqual(responses[0]["result"]["config"], json.loads(live))
        self.assertTrue(responses[1]["ok"])
        restored = [input_text for arguments, input_text in calls if arguments[:3] == ["sudo", "-n", "tee"]]
        self.assertEqual(restored, [live])

    def test_open_run_keeps_a_snapshot_left_by_a_killed_run(self):
        original = '{"viewer": {"mode": "direct"}}'
        reads: list[list[str]] = []

        def run_command(arguments, input_text=None, timeout=0):
            reads.append(arguments)
            return completed('{"viewer": {"mode": "relay"}}')

        with tempfile.TemporaryDirectory() as directory:
            snapshot = f"{directory}/snapshot.json"
            with open(snapshot, "w", encoding="utf-8") as handle:
                handle.write(original)
            with patch.object(streamer_agent, "SNAPSHOT_PATH", snapshot):
                responses = self.serve([{"id": 1, "command": "open_run"}], run_command)
            with open(snapshot, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), original)

        self.assertEqual(responses[0]["result"]["config"], {"viewer": {"mode": "direct"}})
        self.assertTrue(responses[0]["result"]["reused"])
        self.assertEqual(reads, [["sudo", "-n", "systemctl", "stop", "v3xctrl-video", "v3xctrl-control"]])

    def test_open_run_stops_a_control_service_left_running_before_the_run(self):
        calls: list[list[str]] = []

        def run_command(arguments, input_text=None, timeout=0):
            calls.append(arguments)
            return completed('{"viewer": {"mode": "relay"}}')

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(streamer_agent, "SNAPSHOT_PATH", f"{directory}/snapshot.json"),
        ):
            responses = self.serve([{"id": 1, "command": "open_run"}], run_command)

        self.assertTrue(responses[0]["ok"])
        self.assertEqual(calls[-1], ["sudo", "-n", "systemctl", "stop", "v3xctrl-video", "v3xctrl-control"])

    def test_close_run_without_a_snapshot_is_an_error(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(streamer_agent, "SNAPSHOT_PATH", f"{directory}/none.json"),
        ):
            responses = self.serve([{"id": 1, "command": "close_run"}], lambda *a, **k: completed())

        self.assertFalse(responses[0]["ok"])
        self.assertIn("no snapshot", responses[0]["error"])

    def test_delete_recording_refuses_paths_outside_the_recording_directory(self):
        def run_command(arguments, input_text=None, timeout=0):
            if arguments[:3] == ["sudo", "-n", "cat"]:
                return completed(json.dumps({"video": {"record": {"path": "/data/recordings"}}}))
            return completed()

        responses = self.serve(
            [{"id": 1, "command": "delete_recording", "path": "/data/config/config.json"}], run_command
        )

        self.assertFalse(responses[0]["ok"])
        self.assertIn("refusing to delete", responses[0]["error"])
