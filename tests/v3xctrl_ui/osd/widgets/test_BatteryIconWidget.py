"""Tests for BatteryIconWidget."""
import os
import unittest
import pygame

# Set SDL to use dummy video driver before importing pygame
os.environ['SDL_VIDEODRIVER'] = 'dummy'

from v3xctrl_ui.osd.widgets.BatteryIconWidget import BatteryIconWidget


class TestBatteryIconWidget(unittest.TestCase):
    """Test BatteryIconWidget battery level rendering."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        pygame.display.set_mode((800, 600))
        self.screen = pygame.Surface((800, 600))
        self.widget = BatteryIconWidget(position=(100, 100), width=60)

    def test_initialization(self):
        """Test widget initialization."""
        assert self.widget.position == (100, 100)
        assert self.widget.width == 60
        assert self.widget.height == 40
        assert len(self.widget.states) == 8

    def test_draw_full_battery(self):
        """Test drawing battery at 100%."""
        self.widget.draw(self.screen, 100)
        # Verify no exception - renders state 7 (full)

    def test_draw_high_battery(self):
        """Test drawing battery at 96%."""
        self.widget.draw(self.screen, 96)
        # Renders state 7

    def test_draw_good_battery(self):
        """Test drawing battery at 86%."""
        self.widget.draw(self.screen, 86)
        # Renders state 6

    def test_draw_medium_battery(self):
        """Test drawing battery at 71%."""
        self.widget.draw(self.screen, 71)
        # Renders state 5

    def test_draw_moderate_battery(self):
        """Test drawing battery at 56%."""
        self.widget.draw(self.screen, 56)
        # Renders state 4

    def test_draw_low_battery(self):
        """Test drawing battery at 41%."""
        self.widget.draw(self.screen, 41)
        # Renders state 3

    def test_draw_very_low_battery(self):
        """Test drawing battery at 26%."""
        self.widget.draw(self.screen, 26)
        # Renders state 2

    def test_draw_critical_battery(self):
        """Test drawing battery at 11%."""
        self.widget.draw(self.screen, 11)
        # Renders state 1

    def test_draw_empty_battery(self):
        """Test drawing battery at 0%."""
        self.widget.draw(self.screen, 0)
        # Renders state 0


if __name__ == '__main__':
    unittest.main()
