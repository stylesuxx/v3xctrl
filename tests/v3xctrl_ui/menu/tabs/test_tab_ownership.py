# Required before importing pygame, otherwise screen might flicker during tests
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"

import tempfile
import unittest
from pathlib import Path

import pygame

from v3xctrl_ui.core.Settings import Settings
from v3xctrl_ui.menu.tabs.FrequenciesTab import FrequenciesTab
from v3xctrl_ui.menu.tabs.GeneralTab import GeneralTab
from v3xctrl_ui.menu.tabs.NetworkTab import NetworkTab
from v3xctrl_ui.menu.tabs.OsdTab import OsdTab


class TestTabOwnership(unittest.TestCase):
    """A tab edits its own copy of a section, so nothing reaches Settings before Save."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "settings.toml"
        self.settings = Settings(str(self.path))

        self.general = GeneralTab(self.settings, width=640, height=480, padding=10, y_offset=0)
        self.frequencies = FrequenciesTab(self.settings, width=640, height=480, padding=10, y_offset=0)
        self.osd = OsdTab(self.settings, width=640, height=480, padding=10, y_offset=0)
        self.network = NetworkTab(self.settings, width=640, height=480, padding=10, y_offset=0)

        self.tabs = [self.general, self.frequencies, self.osd, self.network]

    def _save_every_tab(self) -> None:
        """What Menu._save_button_callback does."""
        for tab in self.tabs:
            for key, value in tab.get_settings().items():
                self.settings.set(key, value)

        self.settings.save()

    def _make_one_edit_per_tab(self) -> None:
        self.general._on_render_ratio_change("99")
        self.frequencies._on_rate_change("main_loop_fps", "75")
        self.osd._on_widget_toggle("clock", True)
        self.network._on_port_change("video", 12345)

    def test_a_frozen_section_is_shared_rather_than_copied(self):
        """A typed section cannot be mutated, so there is nothing to protect against."""
        self.assertIs(self.network.ports, self.settings.ports)
        self.assertIs(self.network.relay, self.settings.relay)
        self.assertIs(self.frequencies.timing, self.settings.timing)
        self.assertIs(self.general.video, self.settings.video)
        self.assertIs(self.osd.widgets, self.settings.widgets)

    def test_editing_a_tab_leaves_settings_untouched(self):
        self._make_one_edit_per_tab()

        self.assertEqual(self.settings.video.render_ratio, 0)
        self.assertEqual(self.settings.get("timing")["main_loop_fps"], 60)
        self.assertEqual(self.settings.widgets.get("clock").display, False)
        self.assertEqual(self.settings.get("ports")["video"], 16384)

    def test_editing_a_tab_leaves_the_config_file_untouched(self):
        self._make_one_edit_per_tab()

        on_disk = Settings(str(self.path))

        self.assertEqual(on_disk.video.render_ratio, 0)
        self.assertEqual(on_disk.get("timing")["main_loop_fps"], 60)
        self.assertEqual(on_disk.get("ports")["video"], 16384)

    def test_saving_commits_every_tab(self):
        """Save is a single button for the whole menu, not for the visible tab."""
        self._make_one_edit_per_tab()

        self._save_every_tab()
        on_disk = Settings(str(self.path))

        self.assertEqual(on_disk.video.render_ratio, 99)
        self.assertEqual(on_disk.get("timing")["main_loop_fps"], 75)
        self.assertEqual(on_disk.widgets.get("clock").display, True)
        self.assertEqual(on_disk.get("ports")["video"], 12345)

    def test_reapplying_settings_discards_uncommitted_edits(self):
        """What Back does, once the menu is reopened."""
        self._make_one_edit_per_tab()

        for tab in self.tabs:
            tab.apply_settings()

        self.assertEqual(self.general.video.render_ratio, 0)
        self.assertEqual(self.frequencies.timing.main_loop_fps, 60)
        self.assertEqual(self.osd.widgets.get("clock").display, False)
        self.assertEqual(self.network.ports.video, 16384)

    def test_fullscreen_toggled_outside_the_menu_keeps_edits_in_progress(self):
        """[F11] works while the menu is open, and must not wipe what is being typed."""
        self.general._on_render_ratio_change("99")

        self.general.apply_fullscreen(True)

        self.assertEqual(self.general.video.fullscreen, True)
        self.assertTrue(self.general.fullscreen_enabled_checkbox.checked)
        self.assertEqual(self.general.video.render_ratio, 99)


if __name__ == "__main__":
    unittest.main()
