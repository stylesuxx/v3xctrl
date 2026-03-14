import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import create_app
from stats import RelayClient


class TestRelayClient(unittest.TestCase):
    def test_socket_path_template(self):
        client = RelayClient(8888)
        self.assertEqual(client.socket_path, "/tmp/udp_relay_command_8888.sock")

    def test_socket_path_different_port(self):
        client = RelayClient(9999)
        self.assertEqual(client.socket_path, "/tmp/udp_relay_command_9999.sock")


class TestStatsAPI(unittest.TestCase):
    def setUp(self):
        self.users_fd, self.users_file = tempfile.mkstemp(suffix=".json")
        users = {"admin": generate_password_hash("secret123")}
        with open(self.users_file, "w") as f:
            json.dump(users, f)

        self.app = create_app(
            relay_ports=[8888, 9999],
            users_file=self.users_file,
            secret_key="test-secret-key",
        )
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.users_fd)
        os.unlink(self.users_file)

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["username"] = "admin"

    def test_api_stats_returns_data_from_multiple_relays(self):
        self._login()

        mock_stats = {
            "session1": {
                "created_at": 1234567890,
                "mappings": [
                    {
                        "address": "10.0.0.1:5000",
                        "role": "STREAMER",
                        "port_type": "VIDEO",
                        "timeout_in_sec": 300,
                    }
                ],
                "spectators": [],
            }
        }

        with patch("stats.RelayClient.get_stats", return_value=mock_stats):
            response = self.client.get("/api/stats")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("relays", data)
        self.assertIn("8888", data["relays"])
        self.assertIn("9999", data["relays"])

        relay_8888 = data["relays"]["8888"]
        self.assertEqual(relay_8888["status"], "ok")
        self.assertIn("session1", relay_8888["sessions"])

    def test_api_stats_handles_relay_error(self):
        self._login()

        with patch("stats.RelayClient.get_stats", side_effect=ConnectionRefusedError("Connection refused")):
            response = self.client.get("/api/stats")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        for port in ["8888", "9999"]:
            self.assertEqual(data["relays"][port]["status"], "error")
            self.assertIn("error", data["relays"][port])

    def test_api_stats_partial_failure(self):
        self._login()

        mock_stats = {"session1": {"created_at": 100, "mappings": [], "spectators": []}}
        call_count = 0

        def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_stats
            raise ConnectionRefusedError("Connection refused")

        with patch("stats.RelayClient.get_stats", side_effect=side_effect):
            response = self.client.get("/api/stats")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        statuses = [relay["status"] for relay in data["relays"].values()]
        self.assertIn("ok", statuses)
        self.assertIn("error", statuses)

    def test_dashboard_renders_when_authenticated(self):
        self._login()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Relay Stats", response.data)
        self.assertIn(b"8888", response.data)
        self.assertIn(b"9999", response.data)


if __name__ == "__main__":
    unittest.main()
