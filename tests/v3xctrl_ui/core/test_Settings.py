# Required before importing pygame, otherwise screen might flicker during tests
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"

import tempfile
import unittest
from pathlib import Path

import pygame
import tomli_w

from v3xctrl_tcp import Transport
from v3xctrl_ui.core.Settings import Settings
from v3xctrl_ui.core.SettingsSchema import PortSettings, RelaySettings, TimingSettings


class TestSettings(unittest.TestCase):
    def setUp(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".toml") as tmp:
            self.path = tmp.name

    def tearDown(self):
        Path(self.path).unlink(missing_ok=True)

    def test_load_defaults_if_file_missing(self):
        Path(self.path).unlink()
        settings = Settings(self.path)
        self.assertEqual(settings.get("show_connection_info"), True)
        self.assertEqual(settings.get("timing").get("main_loop_fps"), 60)
        self.assertEqual(settings.video.width, 1280)

    def test_save_and_load_round_trip(self):
        settings = Settings(self.path)
        settings.set("show_connection_info", False)
        settings.set("video", {"width": 640, "height": 480})
        settings.save()

        loaded = Settings(self.path)
        self.assertEqual(loaded.get("show_connection_info"), False)
        self.assertEqual(loaded.get("video")["width"], 640)
        self.assertEqual(loaded.get("video")["height"], 480)

    def test_save_and_load_round_trip_one(self):
        settings = Settings(self.path)
        settings.set("show_connection_info", False)
        settings.set("video", {"width": 640, "height": 480})
        settings.save()

        loaded = Settings(self.path)
        self.assertEqual(loaded.get("show_connection_info"), False)
        self.assertEqual(loaded.get("video")["width"], 640)
        self.assertEqual(loaded.get("video")["height"], 480)

    def test_merge_partial_override(self):
        partial = {"video": {"width": 800}, "controls": {"keyboard": {"throttle_up": "K_UP"}}}
        with open(self.path, "wb") as f:
            f.write(tomli_w.dumps(partial).encode("utf-8"))

        settings = Settings(self.path)
        self.assertEqual(settings.video.width, 800)
        self.assertEqual(settings.video.height, 720)
        self.assertEqual(settings.controls.keyboard.throttle_up, pygame.K_UP)
        self.assertEqual(settings.controls.keyboard.throttle_down, pygame.K_s)

    def test_delete_resets_a_scalar_to_its_default(self):
        settings = Settings(self.path)
        settings.set("show_connection_info", False)

        settings.delete("show_connection_info")

        self.assertEqual(settings.show_connection_info, True)

    def test_custom_path_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "nested" / "dir" / "config.toml"
            settings = Settings(str(nested_path))
            self.assertTrue(nested_path.exists())
            self.assertEqual(settings.path, nested_path)

    def test_custom_path_creates_file_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "custom_config.toml"
            self.assertFalse(config_path.exists())
            settings = Settings(str(config_path))
            self.assertTrue(config_path.exists())
            self.assertEqual(settings.get("show_connection_info"), True)
            self.assertEqual(settings.get("timing").get("main_loop_fps"), 60)

    def test_custom_path_preserves_path_attribute(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "my_settings.toml"
            settings = Settings(str(config_path))
            self.assertEqual(settings.path, config_path)


class TestTypedSections(unittest.TestCase):
    def setUp(self):
        self.path = str(Path(tempfile.mkdtemp()) / "settings.toml")

    def _write(self, raw: dict) -> None:
        with open(self.path, "wb") as f:
            f.write(tomli_w.dumps(raw).encode("utf-8"))

    def test_sections_are_parsed_at_load(self):
        settings = Settings(self.path)

        self.assertEqual(settings.ports, PortSettings())
        self.assertEqual(settings.relay, RelaySettings())
        self.assertEqual(settings.timing, TimingSettings())
        self.assertEqual(settings.transport, Transport.UDP)

    def test_every_key_is_typed(self):
        """Nothing is left in the untyped leftover dict for a stock config."""
        settings = Settings(self.path)

        self.assertEqual(settings.settings, {})

    def test_values_from_the_file_reach_the_section(self):
        self._write({"ports": {"video": 9999}, "transport": "tcp"})
        settings = Settings(self.path)

        self.assertEqual(settings.ports.video, 9999)
        self.assertEqual(settings.ports.control, 16386)
        self.assertEqual(settings.transport, Transport.TCP)

    def test_a_bad_value_in_the_file_falls_back_without_stopping_the_load(self):
        self._write({"ports": {"video": "banana", "control": 9999}, "transport": "quic"})

        with self.assertLogs("v3xctrl_ui.core.SettingsSchema", level="WARNING"):
            settings = Settings(self.path)

        self.assertEqual(settings.ports.video, 16384)
        self.assertEqual(settings.ports.control, 9999)
        self.assertEqual(settings.transport, Transport.UDP)

    def test_sections_round_trip_through_the_file(self):
        settings = Settings(self.path)
        settings.ports = PortSettings(video=1234, control=5678)
        settings.relay = RelaySettings(enabled=True, server="example.com:1", id="abc", spectator_mode=True)
        settings.transport = Transport.TCP
        settings.save()

        loaded = Settings(self.path)

        self.assertEqual(loaded.ports, settings.ports)
        self.assertEqual(loaded.relay, settings.relay)
        self.assertEqual(loaded.transport, Transport.TCP)

    def test_get_still_hands_out_a_plain_table(self):
        settings = Settings(self.path)

        self.assertEqual(settings.get("ports"), {"video": 16384, "control": 16386})
        self.assertEqual(settings.get("transport"), Transport.UDP)

    def test_a_table_from_get_is_not_wired_back_into_the_section(self):
        settings = Settings(self.path)

        settings.get("ports")["video"] = 9999

        self.assertEqual(settings.ports.video, 16384)

    def test_set_accepts_a_table(self):
        settings = Settings(self.path)

        settings.set("ports", {"video": 9999, "control": 8888})

        self.assertEqual(settings.ports, PortSettings(video=9999, control=8888))

    def test_set_accepts_a_section(self):
        settings = Settings(self.path)

        settings.set("ports", PortSettings(video=9999, control=8888))

        self.assertEqual(settings.ports, PortSettings(video=9999, control=8888))

    def test_delete_resets_a_section_to_its_defaults(self):
        settings = Settings(self.path)
        settings.ports = PortSettings(video=9999)

        settings.delete("ports")

        self.assertEqual(settings.ports, PortSettings())

    def test_an_existing_file_is_not_rewritten_on_construction(self):
        self._write({"ports": {"video": 9999}})
        before = Path(self.path).read_bytes()

        Settings(self.path)

        self.assertEqual(Path(self.path).read_bytes(), before)


if __name__ == "__main__":
    pygame.init()
    unittest.main()
