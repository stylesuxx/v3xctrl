import argparse
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from main import DEFAULT_PORT, resolve_settings

CONFIG = """
[paths]
users_file = "/var/lib/v3xctrl/users.json"
runtime_directory = "/run/v3xctrl"

[stats]
relay_ports = [8888, 9999]
port = 8080
secret_key = "config-secret"
"""


class TestLoad(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "relay.toml"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_file_yields_empty_config(self):
        self.assertEqual(config.load(self.config_path), {})

    def test_malformed_file_reports_path(self):
        self.config_path.write_text("[stats\nport = 1\n")

        with self.assertRaises(config.ConfigError) as raised:
            config.load(self.config_path)

        self.assertIn(str(self.config_path), str(raised.exception))


class TestRelayPorts(unittest.TestCase):
    def test_missing_list_yields_no_ports(self):
        self.assertEqual(config.get_relay_ports({}), [])

    def test_reads_port_numbers(self):
        self.assertEqual(config.get_relay_ports({"relay_ports": [8888, 9999]}), [8888, 9999])

    def test_rejects_a_non_list(self):
        with self.assertRaises(config.ConfigError):
            config.get_relay_ports({"relay_ports": "8888 9999"})

    def test_rejects_a_non_numeric_entry(self):
        with self.assertRaises(config.ConfigError) as raised:
            config.get_relay_ports({"relay_ports": [8888, "9999"]})

        self.assertIn("9999", str(raised.exception))

    def test_rejects_a_boolean_entry(self):
        with self.assertRaises(config.ConfigError):
            config.get_relay_ports({"relay_ports": [True]})


class TestResolveSettings(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "relay.toml"
        self.config_path.write_text(CONFIG)
        self.missing_path = Path(self.temp_dir.name) / "absent.toml"

    def tearDown(self):
        self.temp_dir.cleanup()

    def arguments(self, **overrides):
        defaults = {
            "relay_ports": None,
            "users_file": None,
            "secret_key": None,
            "port": None,
            "runtime_directory": None,
            "config": str(self.config_path),
        }
        defaults.update(overrides)

        return argparse.Namespace(**defaults)

    def test_reads_the_stats_table(self):
        relay_ports, users_file, secret_key, port, runtime_directory = resolve_settings(self.arguments())

        self.assertEqual(relay_ports, [8888, 9999])
        self.assertEqual(users_file, "/var/lib/v3xctrl/users.json")
        self.assertEqual(secret_key, "config-secret")
        self.assertEqual(port, 8080)
        self.assertEqual(runtime_directory, "/run/v3xctrl")

    def test_arguments_win_over_the_config(self):
        relay_ports, users_file, _, port, _ = resolve_settings(
            self.arguments(relay_ports=[7777], users_file="/tmp/users.json", port=9090)
        )

        self.assertEqual(relay_ports, [7777])
        self.assertEqual(users_file, "/tmp/users.json")
        self.assertEqual(port, 9090)

    def test_missing_relay_ports_names_the_argument(self):
        with self.assertRaises(config.ConfigError) as raised:
            resolve_settings(self.arguments(config=str(self.missing_path), users_file="/tmp/users.json"))

        self.assertIn("--relay-port", str(raised.exception))

    def test_missing_users_file_names_the_argument(self):
        with self.assertRaises(config.ConfigError) as raised:
            resolve_settings(self.arguments(config=str(self.missing_path), relay_ports=[8888]))

        self.assertIn("--users-file", str(raised.exception))

    def test_without_a_config_a_secret_key_is_generated(self):
        arguments = self.arguments(config=str(self.missing_path), relay_ports=[8888], users_file="/tmp/users.json")
        _, _, secret_key, port, _ = resolve_settings(arguments)

        self.assertTrue(secret_key)
        self.assertEqual(port, DEFAULT_PORT)
