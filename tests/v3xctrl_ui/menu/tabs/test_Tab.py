import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import MagicMock, patch
import pygame
from pygame import Surface
from typing import Dict, Any

from v3xctrl_ui.menu.tabs.Tab import Tab
from v3xctrl_ui.Settings import Settings


class ConcreteTab(Tab):
    """Concrete implementation of Tab for testing purposes"""

    def get_settings(self) -> Dict[str, Any]:
        return {"test_setting": "test_value"}

    def draw(self, surface: Surface) -> None:
        # Simple implementation for testing
        self._draw_headline(surface, "Test Tab", self.y_offset)


class TestTab(unittest.TestCase):
    def setUp(self):
        # Initialize pygame for surface creation
        pygame.init()
        pygame.display.set_mode((1, 1))  # Minimal display for testing

        # Mock dependencies
        self.mock_settings = MagicMock(spec=Settings)

        # Test parameters
        self.width = 800
        self.height = 600
        self.padding = 10
        self.y_offset = 20

        # Create concrete Tab instance for testing
        self.tab = ConcreteTab(
            settings=self.mock_settings,
            width=self.width,
            height=self.height,
            padding=self.padding,
            y_offset=self.y_offset
        )

    def tearDown(self):
        pygame.quit()

    def test_initialization(self):
        """Test that Tab initializes correctly"""
        self.assertEqual(self.tab.settings, self.mock_settings)
        self.assertEqual(self.tab.width, self.width)
        self.assertEqual(self.tab.height, self.height)
        self.assertEqual(self.tab.padding, self.padding)
        self.assertEqual(self.tab.y_offset, self.y_offset)

        # Check default values
        self.assertEqual(self.tab.y_offset_headline, 55)
        self.assertEqual(self.tab.y_element_padding, 10)
        self.assertEqual(self.tab.y_section_padding, 25)
        self.assertEqual(self.tab.y_note_padding, 14)
        self.assertEqual(self.tab.y_note_padding_bottom, 5)

        # Check elements list is initialized
        self.assertIsInstance(self.tab.elements, list)
        self.assertEqual(len(self.tab.elements), 0)

    def test_abstract_base_class(self):
        """Test that Tab cannot be instantiated directly"""
        with self.assertRaises(TypeError):
            Tab(
                settings=self.mock_settings,
                width=self.width,
                height=self.height,
                padding=self.padding,
                y_offset=self.y_offset
            )

    @patch('v3xctrl_ui.menu.tabs.Tab.MAIN_FONT')
    @patch('pygame.draw.line')
    def test_draw_headline_without_top_line(self, mock_draw_line, mock_font):
        """Test _draw_headline method without top line"""
        # Mock font rendering
        mock_text_surface = MagicMock()
        mock_text_surface.get_height.return_value = 20
        mock_font.render.return_value = (mock_text_surface, MagicMock())

        surface = MagicMock()
        title = "Test Title"
        y = 50

        result = self.tab._draw_headline(surface, title, y, draw_top_line=False)

        # Check font rendering was called
        mock_font.render.assert_called_once_with(title, unittest.mock.ANY)  # WHITE color

        # Check surface.blit was called
        surface.blit.assert_called_once_with(mock_text_surface, (self.padding, y))

        # Check only bottom line was drawn (1 call)
        self.assertEqual(mock_draw_line.call_count, 1)

        # Check return value
        self.assertEqual(result, y + 40)

    @patch('v3xctrl_ui.menu.tabs.Tab.MAIN_FONT')
    @patch('pygame.draw.line')
    def test_draw_headline_with_top_line(self, mock_draw_line, mock_font):
        """Test _draw_headline method with top line"""
        # Mock font rendering
        mock_text_surface = MagicMock()
        mock_text_surface.get_height.return_value = 20
        mock_font.render.return_value = (mock_text_surface, MagicMock())

        surface = MagicMock()
        title = "Test Title"
        y = 50

        result = self.tab._draw_headline(surface, title, y, draw_top_line=True)

        # Check font rendering was called
        mock_font.render.assert_called_once_with(title, unittest.mock.ANY)  # WHITE color

        # Check surface.blit was called
        surface.blit.assert_called_once_with(mock_text_surface, (self.padding, y))

        # Check both top and bottom lines were drawn (2 calls)
        self.assertEqual(mock_draw_line.call_count, 2)

        # Check return value
        self.assertEqual(result, y + 40)

    @patch('v3xctrl_ui.menu.tabs.Tab.TEXT_FONT')
    def test_draw_note(self, mock_font):
        """Test _draw_note method"""
        # Mock font rendering
        mock_note_surface = MagicMock()
        mock_note_rect = MagicMock()
        mock_note_rect.height = 15
        mock_note_rect.topleft = (0, 0)  # Will be set by the method
        mock_font.render.return_value = (mock_note_surface, mock_note_rect)

        surface = MagicMock()
        text = "Test note"
        y = 100

        result = self.tab._draw_note(surface, text, y)

        # Check font rendering was called
        mock_font.render.assert_called_once_with(text, unittest.mock.ANY)  # WHITE color

        # Check rect position was set
        self.assertEqual(mock_note_rect.topleft, (self.padding, y))

        # Check surface.blit was called
        surface.blit.assert_called_once_with(mock_note_surface, mock_note_rect)

        # Check return value
        self.assertEqual(result, y + mock_note_rect.height)

    def test_handle_event(self):
        """Test handle_event method distributes events to elements"""
        # Create mock elements
        element1 = MagicMock()
        element2 = MagicMock()
        element3 = MagicMock()

        self.tab.elements = [element1, element2, element3]

        # Create mock event
        mock_event = MagicMock()

        # Call handle_event
        self.tab.handle_event(mock_event)

        # Check that all elements received the event
        element1.handle_event.assert_called_once_with(mock_event)
        element2.handle_event.assert_called_once_with(mock_event)
        element3.handle_event.assert_called_once_with(mock_event)

    def test_handle_event_empty_elements(self):
        """Test handle_event method with no elements"""
        # Ensure elements list is empty
        self.tab.elements = []

        # Create mock event
        mock_event = MagicMock()

        # Should not raise exception
        self.tab.handle_event(mock_event)

    def test_concrete_implementation_get_settings(self):
        """Test that concrete implementation can override get_settings"""
        settings = self.tab.get_settings()
        self.assertEqual(settings, {"test_setting": "test_value"})

    @patch('v3xctrl_ui.menu.tabs.Tab.MAIN_FONT')
    @patch('pygame.draw.line')
    def test_concrete_implementation_draw(self, mock_draw_line, mock_font):
        """Test that concrete implementation can override draw method"""
        # Mock font rendering
        mock_text_surface = MagicMock()
        mock_text_surface.get_height.return_value = 20
        mock_font.render.return_value = (mock_text_surface, MagicMock())

        surface = MagicMock()

        # Should not raise exception
        self.tab.draw(surface)

        # Verify that _draw_headline was called internally
        mock_font.render.assert_called_once()

    def test_elements_list_manipulation(self):
        """Test that elements list can be manipulated"""
        # Initially empty
        self.assertEqual(len(self.tab.elements), 0)

        # Add elements
        element1 = MagicMock()
        element2 = MagicMock()

        self.tab.elements.append(element1)
        self.tab.elements.append(element2)

        self.assertEqual(len(self.tab.elements), 2)
        self.assertIn(element1, self.tab.elements)
        self.assertIn(element2, self.tab.elements)

        # Remove element
        self.tab.elements.remove(element1)
        self.assertEqual(len(self.tab.elements), 1)
        self.assertNotIn(element1, self.tab.elements)
        self.assertIn(element2, self.tab.elements)

    def test_headline_drawing_parameters(self):
        """Test that headline drawing uses correct parameters"""
        with patch('v3xctrl_ui.menu.tabs.Tab.MAIN_FONT') as mock_font, \
             patch('pygame.draw.line') as mock_draw_line:

            # Mock font rendering
            mock_text_surface = MagicMock()
            mock_text_surface.get_height.return_value = 25
            mock_font.render.return_value = (mock_text_surface, MagicMock())

            surface = MagicMock()
            title = "Test"
            y = 60

            self.tab._draw_headline(surface, title, y, draw_top_line=True)

            # Check line drawing parameters
            self.assertEqual(mock_draw_line.call_count, 2)

            # Get the call arguments
            calls = mock_draw_line.call_args_list

            # Top line call
            top_line_args = calls[0][0]
            self.assertEqual(top_line_args[0], surface)  # surface
            # Color should be WHITE
            self.assertEqual(top_line_args[2], (self.padding, y - 10 - 2))  # start point
            self.assertEqual(top_line_args[3], (self.width - self.padding, y - 10 - 2))  # end point
            self.assertEqual(top_line_args[4], 2)  # line width

            # Bottom line call
            bottom_line_args = calls[1][0]
            self.assertEqual(bottom_line_args[0], surface)  # surface
            # Color should be WHITE
            self.assertEqual(bottom_line_args[2], (self.padding, y + 25 + 10))  # start point
            self.assertEqual(bottom_line_args[3], (self.width - self.padding, y + 25 + 10))  # end point
            self.assertEqual(bottom_line_args[4], 2)  # line width

    def test_constants_are_accessible(self):
        """Test that all constants are properly set and accessible"""
        # Test all the y-offset constants
        self.assertIsInstance(self.tab.y_offset_headline, int)
        self.assertIsInstance(self.tab.y_element_padding, int)
        self.assertIsInstance(self.tab.y_section_padding, int)
        self.assertIsInstance(self.tab.y_note_padding, int)
        self.assertIsInstance(self.tab.y_note_padding_bottom, int)

        # Test that they have expected values
        self.assertGreater(self.tab.y_offset_headline, 0)
        self.assertGreater(self.tab.y_element_padding, 0)
        self.assertGreater(self.tab.y_section_padding, 0)
        self.assertGreater(self.tab.y_note_padding, 0)
        self.assertGreater(self.tab.y_note_padding_bottom, 0)


class IncompleteTab(Tab):
    """Tab implementation that doesn't override abstract methods"""
    pass


class TestTabAbstractMethods(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.mock_settings = MagicMock(spec=Settings)

    def tearDown(self):
        pygame.quit()

    def test_cannot_instantiate_incomplete_tab(self):
        """Test that Tab subclass without abstract method implementations cannot be instantiated"""
        with self.assertRaises(TypeError) as context:
            IncompleteTab(
                settings=self.mock_settings,
                width=800,
                height=600,
                padding=10,
                y_offset=20
            )

        # Check that the error mentions the abstract methods
        error_message = str(context.exception)
        self.assertIn("abstract", error_message.lower())


if __name__ == '__main__':
    unittest.main()