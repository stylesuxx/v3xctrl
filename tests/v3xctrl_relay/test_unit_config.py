import tempfile
import unittest
from pathlib import Path

from v3xctrl_relay import config


class TestLoad(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "relay.toml"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_file_yields_empty_config(self):
        self.assertEqual(config.load(self.config_path), {})

    def test_reads_tables(self):
        self.config_path.write_text('[paths]\ndatabase = "/var/lib/v3xctrl/relay.db"\n')

        self.assertEqual(config.load(self.config_path), {"paths": {"database": "/var/lib/v3xctrl/relay.db"}})

    def test_malformed_file_reports_path(self):
        self.config_path.write_text("[paths\ndatabase = 1\n")

        with self.assertRaises(config.ConfigError) as raised:
            config.load(self.config_path)

        self.assertIn(str(self.config_path), str(raised.exception))

    def test_directory_instead_of_file_reports_path(self):
        directory = Path(self.temp_dir.name) / "subdirectory"
        directory.mkdir()

        with self.assertRaises(config.ConfigError) as raised:
            config.load(directory)

        self.assertIn(str(directory), str(raised.exception))


class TestSection(unittest.TestCase):
    def test_missing_section_yields_empty_table(self):
        self.assertEqual(config.get_section({}, "paths"), {})

    def test_missing_nested_section_yields_empty_table(self):
        self.assertEqual(config.get_section({"relay": {}}, "relay", "prod"), {})

    def test_reads_nested_section(self):
        loaded = {"relay": {"prod": {"port": 8888}}}

        self.assertEqual(config.get_section(loaded, "relay", "prod"), {"port": 8888})

    def test_non_table_value_names_the_path(self):
        loaded = {"relay": {"prod": 8888}}

        with self.assertRaises(config.ConfigError) as raised:
            config.get_section(loaded, "relay", "prod")

        self.assertIn("relay.prod", str(raised.exception))


class TestRequire(unittest.TestCase):
    def test_passes_a_value_through(self):
        self.assertEqual(config.require("value", "name", "--name"), "value")

    def test_keeps_falsy_values(self):
        self.assertEqual(config.require(0, "name", "--name"), 0)

    def test_missing_value_names_the_argument(self):
        with self.assertRaises(config.ConfigError) as raised:
            config.require(None, "token", "the token argument")

        self.assertIn("token", str(raised.exception))
        self.assertIn("the token argument", str(raised.exception))
