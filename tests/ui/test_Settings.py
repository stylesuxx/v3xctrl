import unittest
import tempfile
from pathlib import Path
import pygame
import tomli_w

from src.ui.Settings import Settings


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.tempfile = tempfile.NamedTemporaryFile(delete=False, suffix=".toml")
        self.path = self.tempfile.name
        self.tempfile.close()

    def tearDown(self):
        Path(self.path).unlink(missing_ok=True)

    def test_load_defaults_if_file_missing(self):
        Path(self.path).unlink()
        settings = Settings(self.path)
        self.assertEqual(settings.get("debug"), True)
        self.assertEqual(settings.get("timing").get("main_loop_fps"), 60)
        self.assertEqual(settings.settings["video"]["width"], 1280)

    def test_save_and_load_round_trip(self):
        settings = Settings(self.path)
        settings.set("debug", False)
        settings.set("video", {"width": 640, "height": 480})
        settings.save()

        loaded = Settings(self.path)
        self.assertEqual(loaded.get("debug"), False)
        self.assertEqual(loaded.get("video")["width"], 640)
        self.assertEqual(loaded.get("video")["height"], 480)

    def test_save_and_load_round_trip_one(self):
        settings = Settings(self.path)
        settings.set("debug", False)
        settings.set("video", {"width": 640, "height": 480})
        settings.save()

        loaded = Settings(self.path)
        self.assertEqual(loaded.get("debug"), False)
        self.assertEqual(loaded.get("video")["width"], 640)
        self.assertEqual(loaded.get("video")["height"], 480)

    def test_merge_partial_override(self):
        partial = {
            "video": {"width": 800},
            "controls": {
                "keyboard": {
                    "throttle_up": "K_UP"
                }
            }
        }
        with open(self.path, "wb") as f:
            f.write(tomli_w.dumps(partial).encode("utf-8"))

        settings = Settings(self.path)
        self.assertEqual(settings.settings["video"]["width"], 800)
        self.assertEqual(settings.settings["video"]["height"], 720)
        self.assertEqual(settings.settings["controls"]["keyboard"]["throttle_up"], pygame.K_UP)
        self.assertEqual(settings.settings["controls"]["keyboard"]["throttle_down"], pygame.K_s)

    def test_delete_key(self):
        settings = Settings(self.path)
        settings.delete("debug")
        self.assertNotIn("debug", settings.settings)


if __name__ == "__main__":
    pygame.init()
    unittest.main()
