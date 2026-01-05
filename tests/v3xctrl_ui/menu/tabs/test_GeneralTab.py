"""Tests for GeneralTab."""
import os
import unittest
from unittest.mock import MagicMock
import pygame

# Set SDL to use dummy video driver
os.environ['SDL_VIDEODRIVER'] = 'dummy'

from v3xctrl_ui.menu.tabs.GeneralTab import GeneralTab
from v3xctrl_ui.utils.Settings import Settings


class TestGeneralTab(unittest.TestCase):
    """Test GeneralTab initialization and methods."""

    @classmethod
    def setUpClass(cls):
        """Initialize pygame once for all tests."""
        pygame.init()
        pygame.display.set_mode((800, 600))

    def setUp(self):
        """Set up test fixtures."""
        self.settings = MagicMock(spec=Settings)
        self.settings.get.side_effect = lambda key, default=None: {
            "video": {"fullscreen": False, "render_ratio": 0},
            "show_connection_info": True
        }.get(key, default)

        self.tab = GeneralTab(
            settings=self.settings,
            width=400,
            height=600,
            padding=10,
            y_offset=20
        )

    def test_initialization(self):
        """Test GeneralTab initializes correctly."""
        assert self.tab.video == {"fullscreen": False, "render_ratio": 0}
        assert self.tab.show_connection_info is True
        assert len(self.tab.elements) == 3
        assert self.tab.fullscreen_enabled_checkbox is not None
        assert self.tab.show_connection_info_checkbox is not None
        assert self.tab.render_ratio_input is not None

    def test_get_settings(self):
        """Test get_settings returns current settings."""
        settings = self.tab.get_settings()

        assert "show_connection_info" in settings
        assert "video" in settings
        assert settings["show_connection_info"] is True
        assert settings["video"]["fullscreen"] is False

    def test_on_render_ratio_change_with_valid_int(self):
        """Test _on_render_ratio_change with valid integer string."""
        self.tab._on_render_ratio_change("50")

        assert self.tab.video["render_ratio"] == 50

    def test_on_render_ratio_change_with_invalid_value(self):
        """Test _on_render_ratio_change with invalid value."""
        original_value = self.tab.video.get("render_ratio", 0)
        self.tab._on_render_ratio_change("not_a_number")

        # Value should not change
        assert self.tab.video.get("render_ratio") == original_value

    def test_on_show_connection_info_change(self):
        """Test _on_show_connection_info_change updates value."""
        self.tab._on_show_connection_info_change(False)
        assert self.tab.show_connection_info is False

        self.tab._on_show_connection_info_change(True)
        assert self.tab.show_connection_info is True

    def test_on_fullscreen_enable_change(self):
        """Test _on_fullscreen_enable_change updates video settings."""
        self.tab._on_fullscreen_enable_change(True)
        assert self.tab.video["fullscreen"] is True

        self.tab._on_fullscreen_enable_change(False)
        assert self.tab.video["fullscreen"] is False

    def test_draw(self):
        """Test draw method doesn't crash."""
        surface = pygame.Surface((400, 600))
        # Should not raise an exception
        self.tab.draw(surface)

    def test_refresh_from_settings(self):
        """Test refresh_from_settings updates widget states."""
        # Change settings mock to return different values
        self.settings.get.side_effect = lambda key, default=None: {
            "video": {"fullscreen": True, "render_ratio": 50},
            "show_connection_info": False
        }.get(key, default)

        # Call refresh
        self.tab.refresh_from_settings()

        # Verify internal state is updated
        assert self.tab.video["fullscreen"] is True
        assert self.tab.video["render_ratio"] == 50
        assert self.tab.show_connection_info is False

        # Verify checkbox states are updated
        assert self.tab.fullscreen_enabled_checkbox.checked is True
        assert self.tab.show_connection_info_checkbox.checked is False

        # Verify input value is updated
        assert self.tab.render_ratio_input.value == "50"


if __name__ == '__main__':
    unittest.main()
