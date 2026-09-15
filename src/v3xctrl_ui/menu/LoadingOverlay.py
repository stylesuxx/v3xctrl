import math
from collections.abc import Callable
from enum import Enum, auto

import pygame
from pygame import Surface

from v3xctrl_ui.utils.colors import TRANSPARENT_BLACK, WHITE
from v3xctrl_ui.utils.fonts import MAIN_FONT
from v3xctrl_ui.utils.i18n import t


class OverlayPhase(Enum):
    HIDDEN = auto()
    WAITING = auto()
    HOLDING_RESULT = auto()


class LoadingOverlay:
    """The menu's modal wait: a spinner, then the outcome, then gone.

    Advancing it and painting it are separate calls, so the outcome stays up
    for a duration rather than for a number of painted frames, and the whole
    sequence can be exercised without a surface.
    """

    BACKGROUND_COLOR = TRANSPARENT_BLACK
    RESULT_DISPLAY_SECONDS = 1.2
    SPINNER_SEGMENTS = 8
    SPINNER_DEGREES_PER_UPDATE = 5
    SPINNER_RADIUS = 30
    SPINNER_THICKNESS = 4
    TEXT_OFFSET = 60

    def __init__(self) -> None:
        self.text = ""
        self.spinner_angle = 0

        self._phase = OverlayPhase.HIDDEN
        self._result: tuple[bool, Callable[[bool], None]] | None = None
        self._hold_started_at = 0.0

    @property
    def is_visible(self) -> bool:
        return self._phase is not OverlayPhase.HIDDEN

    def show(self, text: str) -> None:
        self.text = text
        self._result = None
        self._phase = OverlayPhase.WAITING

    def show_result(self, is_success: bool, on_dismissed: Callable[[bool], None]) -> None:
        self._result = (is_success, on_dismissed)

    def update(self, now: float) -> None:
        """Advance the spinner and the result hold. Call once per loop iteration."""
        match self._phase:
            case OverlayPhase.HIDDEN:
                return

            case OverlayPhase.WAITING:
                self._advance_spinner()
                self._begin_result_hold(now)

            case OverlayPhase.HOLDING_RESULT:
                self._advance_spinner()
                self._end_result_hold(now)

    def draw(self, surface: Surface) -> None:
        width, height = surface.get_size()

        background = pygame.Surface((width, height), pygame.SRCALPHA)
        background.fill(self.BACKGROUND_COLOR)
        surface.blit(background, (0, 0))

        center_x = width // 2
        center_y = height // 2

        # Each segment is dimmer than the last, which reads as a spinning arc
        for segment in range(self.SPINNER_SEGMENTS):
            segment_angle = (self.spinner_angle + segment * (360 / self.SPINNER_SEGMENTS)) % 360
            angle_radians = math.radians(segment_angle)

            x = center_x + int(self.SPINNER_RADIUS * math.cos(angle_radians))
            y = center_y + int(self.SPINNER_RADIUS * math.sin(angle_radians))
            alpha = int(255 * (segment / self.SPINNER_SEGMENTS))

            pygame.draw.circle(surface, (*WHITE, alpha), (x, y), self.SPINNER_THICKNESS)

        text_surface, text_rect = MAIN_FONT.render(self.text, WHITE)
        text_rect.center = (center_x, center_y + self.TEXT_OFFSET)
        surface.blit(text_surface, text_rect)

    def _advance_spinner(self) -> None:
        self.spinner_angle = (self.spinner_angle + self.SPINNER_DEGREES_PER_UPDATE) % 360

    def _begin_result_hold(self, now: float) -> None:
        if self._result is None:
            return

        is_success, _ = self._result
        self.text = t("Success!") if is_success else t("Failed!")
        self._hold_started_at = now
        self._phase = OverlayPhase.HOLDING_RESULT

    def _end_result_hold(self, now: float) -> None:
        # HOLDING_RESULT is only ever entered with a result in hand
        if self._result is None:
            return

        if now - self._hold_started_at < self.RESULT_DISPLAY_SECONDS:
            return

        is_success, on_dismissed = self._result
        self._result = None
        self._phase = OverlayPhase.HIDDEN

        on_dismissed(is_success)
