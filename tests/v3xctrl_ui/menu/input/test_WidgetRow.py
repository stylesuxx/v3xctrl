import os

os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest

import pygame
from pygame.event import Event
from pygame.locals import MOUSEMOTION

from v3xctrl_ui.menu.input.BaseWidget import BaseWidget
from v3xctrl_ui.menu.input.WidgetRow import WidgetRow


class RecordingWidget(BaseWidget):
    def __init__(self, handles: bool) -> None:
        super().__init__()
        self.handles = handles
        self.seen: list[Event] = []

    def handle_event(self, event: Event) -> bool:
        self.seen.append(event)
        return self.handles

    def get_size(self) -> tuple[int, int]:
        return (40, 20)

    def _draw(self, surface: pygame.Surface) -> None:
        pass


class TestWidgetRow(unittest.TestCase):
    def test_every_child_sees_the_event_when_the_first_handles_it(self):
        first = RecordingWidget(handles=True)
        second = RecordingWidget(handles=False)
        row = WidgetRow([first, second])
        motion = Event(MOUSEMOTION, {"pos": (5, 5)})

        handled = row.handle_event(motion)

        self.assertTrue(handled)
        self.assertEqual(first.seen, [motion])
        self.assertEqual(second.seen, [motion])

    def test_reports_unhandled_when_no_child_handles(self):
        row = WidgetRow([RecordingWidget(handles=False), RecordingWidget(handles=False)])

        self.assertFalse(row.handle_event(Event(MOUSEMOTION, {"pos": (5, 5)})))
