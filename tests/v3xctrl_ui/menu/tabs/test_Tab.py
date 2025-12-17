# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock, patch

import pygame
from pygame import Surface
from typing import Dict, Any

from v3xctrl_ui.menu.tabs.Tab import Tab
from v3xctrl_ui.utils.Settings import Settings


class ConcreteTab(Tab):
    def __init__(self, settings, width, height, padding, y_offset):
        super().__init__(settings, width, height, padding, y_offset)
        # Pre-render headlines during initialization
        self.headline_surfaces["main"] = self._create_headline("Test Tab", draw_top_line=False)

    def get_settings(self) -> Dict[str, Any]:
        return {"test_setting": "test_value"}

    def draw(self, surface: Surface) -> None:
        self._draw_headline(surface, "main", self.y_offset)


class TestTab(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))

        self.mock_settings = MagicMock(spec=Settings)

        self.width = 800
        self.height = 600
        self.padding = 10
        self.y_offset = 20

        self.tab = ConcreteTab(
            settings=self.mock_settings,
            width=self.width,
            height=self.height,
            padding=self.padding,
            y_offset=self.y_offset
        )

    def test_initialization(self):
        self.assertEqual(self.tab.settings, self.mock_settings)
        self.assertEqual(self.tab.width, self.width)
        self.assertEqual(self.tab.height, self.height)
        self.assertEqual(self.tab.padding, self.padding)
        self.assertEqual(self.tab.y_offset, self.y_offset)

        self.assertEqual(self.tab.y_offset_headline, 55)
        self.assertEqual(self.tab.y_element_padding, 10)
        self.assertEqual(self.tab.y_section_padding, 25)
        self.assertEqual(self.tab.y_note_padding, 14)
        self.assertEqual(self.tab.y_note_padding_bottom, 5)

        self.assertIsInstance(self.tab.elements, list)
        self.assertEqual(len(self.tab.elements), 0)

        self.assertIsInstance(self.tab.headline_surfaces, dict)

    def test_abstract_base_class(self):
        with self.assertRaises(TypeError):
            Tab(
                settings=self.mock_settings,
                width=self.width,
                height=self.height,
                padding=self.padding,
                y_offset=self.y_offset
            )

    def test_headline_surfaces_initialized(self):
        """Test that headline_surfaces dict is created during initialization"""
        self.assertIsInstance(self.tab.headline_surfaces, dict)

    def test_concrete_tab_pre_renders_headlines(self):
        """Test that ConcreteTab pre-renders its headlines"""
        self.assertIn("main", self.tab.headline_surfaces)
        self.assertIsInstance(self.tab.headline_surfaces["main"], Surface)

    @patch('pygame.draw.line')
    def test_create_headline_without_top_line(self, mock_draw_line):
        """Test _create_headline creates a surface without top line"""
        surface = self.tab._create_headline("Test Title", draw_top_line=False)

        self.assertIsInstance(surface, Surface)

        # Should draw only 1 line (bottom line)
        self.assertEqual(mock_draw_line.call_count, 1)

    @patch('pygame.draw.line')
    def test_create_headline_with_top_line(self, mock_draw_line):
        """Test _create_headline creates a surface with top line"""
        surface = self.tab._create_headline("Test Title", draw_top_line=True)

        self.assertIsInstance(surface, Surface)

        # Should draw 2 lines (top and bottom)
        self.assertEqual(mock_draw_line.call_count, 2)

    def test_draw_headline_returns_height(self):
        """Test that _draw_headline returns the height of the headline"""
        surface = MagicMock()
        y = 50

        height = self.tab._draw_headline(surface, "main", y)

        self.assertIsInstance(height, int)
        self.assertGreater(height, 0)

        # Should match the actual headline surface height
        expected_height = self.tab.headline_surfaces["main"].get_height()
        self.assertEqual(height, expected_height)

    def test_draw_headline_blits_at_correct_position(self):
        """Test that _draw_headline blits the headline at the correct position"""
        surface = MagicMock()
        y = 100

        self.tab._draw_headline(surface, "main", y)

        # Should blit the pre-rendered headline
        surface.blit.assert_called_once()
        args = surface.blit.call_args[0]

        # First arg should be the headline surface
        self.assertEqual(args[0], self.tab.headline_surfaces["main"])

        # Second arg should be the position (padding, y)
        self.assertEqual(args[1], (self.padding, y))

    def test_draw_headline_missing_key_raises_error(self):
        """Test that _draw_headline raises KeyError if headline wasn't pre-rendered"""
        surface = MagicMock()

        with self.assertRaises(KeyError) as context:
            self.tab._draw_headline(surface, "nonexistent", 50)

        error_message = str(context.exception)
        self.assertIn("nonexistent", error_message)
        self.assertIn("not found", error_message.lower())

    @patch('v3xctrl_ui.menu.tabs.Tab.TEXT_FONT')
    def test_draw_note(self, mock_font):
        mock_note_surface = MagicMock()
        mock_note_rect = MagicMock()
        mock_note_rect.height = 15
        mock_note_rect.topleft = (0, 0)
        mock_font.render.return_value = (mock_note_surface, mock_note_rect)

        surface = MagicMock()
        text = "Test note"
        y = 100

        self.assertEqual(
            self.tab._draw_note(surface, text, y),
            y + mock_note_rect.height
        )

        mock_font.render.assert_called_once_with(text, unittest.mock.ANY)

        self.assertEqual(mock_note_rect.topleft, (self.padding, y))

        surface.blit.assert_called_once_with(mock_note_surface, mock_note_rect)

    def test_handle_event(self):
        element1 = MagicMock()
        element2 = MagicMock()
        element3 = MagicMock()

        self.tab.elements = [element1, element2, element3]

        mock_event = MagicMock()

        self.tab.handle_event(mock_event)

        element1.handle_event.assert_called_once_with(mock_event)
        element2.handle_event.assert_called_once_with(mock_event)
        element3.handle_event.assert_called_once_with(mock_event)

    def test_handle_event_empty_elements(self):
        self.tab.elements = []

        mock_event = MagicMock()

        self.tab.handle_event(mock_event)

    def test_concrete_implementation_get_settings(self):
        self.assertEqual(self.tab.get_settings(), {"test_setting": "test_value"})

    def test_concrete_implementation_draw(self):
        """Test that concrete tab's draw method works"""
        surface = MagicMock()

        try:
            self.tab.draw(surface)
        except Exception as e:
            self.fail(f"draw() raised an exception: {e}")

        # Should have called blit at least once (for the headline)
        surface.blit.assert_called()

    def test_elements_list_manipulation(self):
        self.assertEqual(len(self.tab.elements), 0)

        element1 = MagicMock()
        element2 = MagicMock()

        self.tab.elements.append(element1)
        self.tab.elements.append(element2)

        self.assertEqual(len(self.tab.elements), 2)
        self.assertIn(element1, self.tab.elements)
        self.assertIn(element2, self.tab.elements)

        self.tab.elements.remove(element1)
        self.assertEqual(len(self.tab.elements), 1)
        self.assertNotIn(element1, self.tab.elements)
        self.assertIn(element2, self.tab.elements)

    def test_create_headline_surface_dimensions(self):
        """Test that _create_headline creates a surface with correct dimensions"""
        # Test without top line
        surface = self.tab._create_headline("Test", draw_top_line=False)

        expected_width = self.width - (2 * self.padding)
        self.assertEqual(surface.get_width(), expected_width)

        # Height should include text + line padding
        self.assertGreater(surface.get_height(), 0)

        # Test with top line should be taller
        surface_with_top = self.tab._create_headline("Test", draw_top_line=True)
        self.assertGreater(surface_with_top.get_height(), surface.get_height())

    @patch('pygame.draw.line')
    def test_create_headline_draws_lines_correctly(self, mock_draw_line):
        """Test that _create_headline draws lines at correct positions"""
        # Test with top line
        self.tab._create_headline("Test", draw_top_line=True)

        self.assertEqual(mock_draw_line.call_count, 2)

        # Both calls should be to draw lines
        for call in mock_draw_line.call_args_list:
            args = call[0]
            # Should have surface, color, start_pos, end_pos, width
            self.assertEqual(len(args), 5)
            # Width should be 2
            self.assertEqual(args[4], 2)

    def test_constants_are_accessible(self):
        self.assertIsInstance(self.tab.y_offset_headline, int)
        self.assertIsInstance(self.tab.y_element_padding, int)
        self.assertIsInstance(self.tab.y_section_padding, int)
        self.assertIsInstance(self.tab.y_note_padding, int)
        self.assertIsInstance(self.tab.y_note_padding_bottom, int)

        self.assertGreater(self.tab.y_offset_headline, 0)
        self.assertGreater(self.tab.y_element_padding, 0)
        self.assertGreater(self.tab.y_section_padding, 0)
        self.assertGreater(self.tab.y_note_padding, 0)
        self.assertGreater(self.tab.y_note_padding_bottom, 0)

    def test_multiple_headlines_can_be_stored(self):
        """Test that multiple headlines can be pre-rendered and stored"""
        headline1 = self.tab._create_headline("Headline 1", draw_top_line=False)
        headline2 = self.tab._create_headline("Headline 2", draw_top_line=True)

        self.tab.headline_surfaces["h1"] = headline1
        self.tab.headline_surfaces["h2"] = headline2

        self.assertEqual(len(self.tab.headline_surfaces), 3)  # main + h1 + h2
        self.assertIn("main", self.tab.headline_surfaces)
        self.assertIn("h1", self.tab.headline_surfaces)
        self.assertIn("h2", self.tab.headline_surfaces)

    def test_draw_headline_does_not_re_render(self):
        """Test that _draw_headline uses cached surface without re-rendering"""
        surface = MagicMock()

        # Get the original headline surface
        original_surface = self.tab.headline_surfaces["main"]

        # Call draw multiple times
        self.tab._draw_headline(surface, "main", 50)
        self.tab._draw_headline(surface, "main", 100)

        # Should still be the same surface object (not re-rendered)
        self.assertIs(self.tab.headline_surfaces["main"], original_surface)


class IncompleteTab(Tab):
    pass


class TestTabAbstractMethods(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.mock_settings = MagicMock(spec=Settings)

    def test_cannot_instantiate_incomplete_tab(self):
        with self.assertRaises(TypeError) as context:
            IncompleteTab(
                settings=self.mock_settings,
                width=800,
                height=600,
                padding=10,
                y_offset=20
            )

        error_message = str(context.exception)
        self.assertIn("abstract", error_message.lower())


if __name__ == '__main__':
    unittest.main()
