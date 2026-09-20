import argparse
import tempfile
import unittest
from pathlib import Path

from v3xctrl_relay import config
from v3xctrl_relay.apps import bot, relayServer

CONFIG = """
[paths]
database = "/var/lib/v3xctrl/relay.db"
runtime_directory = "/run/v3xctrl"

[relay.prod]
bind_ip = "203.0.113.1"
port = 8888
log = "INFO"

[bot]
token = "config-token"
channel_id = 111
testdrive_channel_id = 222
log = "WARNING"
"""


class ResolutionTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "relay.toml"
        self.config_path.write_text(CONFIG)
        self.missing_path = Path(self.temp_dir.name) / "absent.toml"

    def tearDown(self):
        self.temp_dir.cleanup()


class TestRelayServerSettings(ResolutionTestCase):
    def arguments(self, **overrides):
        defaults = {
            "ip": None,
            "port": None,
            "log": None,
            "db_path": None,
            "runtime_directory": None,
            "instance": None,
            "config": str(self.config_path),
        }
        defaults.update(overrides)

        return argparse.Namespace(**defaults)

    def test_reads_the_named_instance(self):
        ip, port, log_level, db_path, runtime_directory = relayServer.resolve_settings(self.arguments(instance="prod"))

        self.assertEqual(ip, "203.0.113.1")
        self.assertEqual(port, 8888)
        self.assertEqual(log_level, "INFO")
        self.assertEqual(db_path, "/var/lib/v3xctrl/relay.db")
        self.assertEqual(runtime_directory, "/run/v3xctrl")

    def test_arguments_win_over_the_config(self):
        ip, port, log_level, _, _ = relayServer.resolve_settings(
            self.arguments(instance="prod", ip="198.51.100.9", port=9999, log="DEBUG")
        )

        self.assertEqual(ip, "198.51.100.9")
        self.assertEqual(port, 9999)
        self.assertEqual(log_level, "DEBUG")

    def test_unknown_instance_names_itself(self):
        with self.assertRaises(config.ConfigError) as raised:
            relayServer.resolve_settings(self.arguments(instance="staging"))

        self.assertIn("relay.staging", str(raised.exception))

    def test_missing_bind_ip_names_the_argument(self):
        with self.assertRaises(config.ConfigError) as raised:
            relayServer.resolve_settings(self.arguments(config=str(self.missing_path)))

        self.assertIn("bind_ip", str(raised.exception))

    def test_without_a_config_the_arguments_carry_everything(self):
        ip, port, log_level, db_path, runtime_directory = relayServer.resolve_settings(
            self.arguments(config=str(self.missing_path), ip="198.51.100.9")
        )

        self.assertEqual(ip, "198.51.100.9")
        self.assertEqual(port, relayServer.DEFAULT_PORT)
        self.assertEqual(log_level, relayServer.DEFAULT_LOG_LEVEL)
        self.assertEqual(db_path, relayServer.DEFAULT_DB_PATH)
        self.assertEqual(runtime_directory, relayServer.DEFAULT_RUNTIME_DIRECTORY)


class TestBotSettings(ResolutionTestCase):
    def arguments(self, **overrides):
        defaults = {
            "token": None,
            "channel_id": None,
            "testdrive_channel_id": None,
            "db_path": None,
            "log": None,
            "config": str(self.config_path),
        }
        defaults.update(overrides)

        return argparse.Namespace(**defaults)

    def test_reads_the_bot_table(self):
        token, channel_id, testdrive_channel_id, log_level, db_path = bot.resolve_settings(self.arguments())

        self.assertEqual(token, "config-token")
        self.assertEqual(channel_id, 111)
        self.assertEqual(testdrive_channel_id, 222)
        self.assertEqual(log_level, "WARNING")
        self.assertEqual(db_path, "/var/lib/v3xctrl/relay.db")

    def test_arguments_win_over_the_config(self):
        token, channel_id, testdrive_channel_id, _, _ = bot.resolve_settings(
            self.arguments(token="argument-token", channel_id=333, testdrive_channel_id=444)
        )

        self.assertEqual(token, "argument-token")
        self.assertEqual(channel_id, 333)
        self.assertEqual(testdrive_channel_id, 444)

    def test_missing_token_names_the_argument(self):
        with self.assertRaises(config.ConfigError) as raised:
            bot.resolve_settings(self.arguments(config=str(self.missing_path), channel_id=1))

        self.assertIn("token", str(raised.exception))

    def test_missing_channel_id_names_the_argument(self):
        with self.assertRaises(config.ConfigError) as raised:
            bot.resolve_settings(self.arguments(config=str(self.missing_path), token="argument-token"))

        self.assertIn("channel_id", str(raised.exception))

    def test_testdrive_channel_stays_optional(self):
        arguments = self.arguments(config=str(self.missing_path), token="argument-token", channel_id=1)
        _, _, testdrive_channel_id, _, _ = bot.resolve_settings(arguments)

        self.assertIsNone(testdrive_channel_id)
