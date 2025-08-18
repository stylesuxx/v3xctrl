import os
import unittest
from unittest.mock import MagicMock, patch

import pygame
from pygame import Surface
from typing import Dict, Any

from v3xctrl_ui.menu.tabs.Tab import Tab
from v3xctrl_ui.Settings import Settings

os.environ["SDL_VIDEODRIVER"] = "dummy"


class ConcreteTab(Tab):
    def get_settings(self) -> Dict[str, Any]:
        return {"test_setting": "test_value"}

    def draw(self, surface: Surface) -> None:
        self._draw_headline(surface, "Test Tab", self.y_offset)


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

    def tearDown(self):
        pygame.quit()

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

    def test_abstract_base_class(self):
        with self.assertRaises(TypeError):
            Tab(
                settings=self.mock_settings,
                width=self.width,
                height=self.height,
                padding=self.padding,
                y_offset=self.y_offset
            )

    @patch('pygame.draw.line')
    @patch('v3xctrl_ui.menu.tabs.Tab.MAIN_FONT')
    def test_draw_headline_without_top_line(self, mock_font, mock_draw_line):
        mock_text_surface = MagicMock()
        mock_text_surface.get_height.return_value = 20
        mock_font.render.return_value = (mock_text_surface, MagicMock())

        surface = MagicMock()
        title = "Test Title"
        y = 50

        self.assertEqual(
            self.tab._draw_headline(surface, title, y, draw_top_line=False),
            y + 40
        )

        mock_font.render.assert_called_once_with(title, unittest.mock.ANY)

        surface.blit.assert_called_once_with(mock_text_surface, (self.padding, y))

        self.assertEqual(mock_draw_line.call_count, 1)

    @patch('pygame.draw.line')
    @patch('v3xctrl_ui.menu.tabs.Tab.MAIN_FONT')
    def test_draw_headline_with_top_line(self, mock_font, mock_draw_line):
        mock_text_surface = MagicMock()
        mock_text_surface.get_height.return_value = 20
        mock_font.render.return_value = (mock_text_surface, MagicMock())

        surface = MagicMock()
        title = "Test Title"
        y = 50

        self.assertEqual(
            self.tab._draw_headline(surface, title, y, draw_top_line=True),
            y + 40
        )

        mock_font.render.assert_called_once_with(title, unittest.mock.ANY)

        surface.blit.assert_called_once_with(mock_text_surface, (self.padding, y))

        self.assertEqual(mock_draw_line.call_count, 2)

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

    @patch('pygame.draw.line')
    @patch('v3xctrl_ui.menu.tabs.Tab.MAIN_FONT')
    def test_concrete_implementation_draw(self, mock_font, mock_draw_line):
        mock_text_surface = MagicMock()
        mock_text_surface.get_height.return_value = 20
        mock_font.render.return_value = (mock_text_surface, MagicMock())

        surface = MagicMock()

        self.tab.draw(surface)

        mock_font.render.assert_called_once()

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

    @patch('pygame.draw.line')
    @patch('v3xctrl_ui.menu.tabs.Tab.MAIN_FONT')
    def test_headline_drawing_parameters(self, mock_font, mock_draw_line):
        mock_text_surface = MagicMock()
        mock_text_surface.get_height.return_value = 25
        mock_font.render.return_value = (mock_text_surface, MagicMock())

        surface = MagicMock()
        title = "Test"
        y = 60

        self.tab._draw_headline(surface, title, y, draw_top_line=True)

        self.assertEqual(mock_draw_line.call_count, 2)

        calls = mock_draw_line.call_args_list

        top_line_args = calls[0][0]
        self.assertEqual(top_line_args[0], surface)
        self.assertEqual(top_line_args[2], (self.padding, y - 10 - 2))
        self.assertEqual(top_line_args[3], (self.width - self.padding, y - 10 - 2))
        self.assertEqual(top_line_args[4], 2)

        bottom_line_args = calls[1][0]
        self.assertEqual(bottom_line_args[0], surface)
        self.assertEqual(bottom_line_args[2], (self.padding, y + 25 + 10))
        self.assertEqual(bottom_line_args[3], (self.width - self.padding, y + 25 + 10))
        self.assertEqual(bottom_line_args[4], 2)

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


class IncompleteTab(Tab):
    pass


class TestTabAbstractMethods(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1, 1))
        self.mock_settings = MagicMock(spec=Settings)

    def tearDown(self):
        pygame.quit()

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
