from collections import deque
from typing import Tuple

import pygame
from pygame import Surface

from v3xctrl_ui.utils.colors import WHITE, GREEN
from v3xctrl_ui.utils.fonts import BOLD_MONO_FONT
from v3xctrl_ui.utils.helpers import get_icon, round_corners
from v3xctrl_ui.osd.widgets.Widget import Widget


class FpsWidget(Widget):
    def __init__(
        self,
        position: Tuple[int, int],
        size: Tuple[int, int],
        label: str,
        smoothing_window: int = 15
    ) -> None:
        super().__init__()

        self.position = position

        self.size = size
        self.width, self.height = self.size

        self.graph_alpha = 180

        self.average_window = 1
        self.graph_frames = 300
        self.history: deque[float] = deque(maxlen=self.graph_frames)
        self.smoothed_fps: deque[int] = deque(maxlen=smoothing_window)

        self.font = BOLD_MONO_FONT

        top_padding = 2
        label_offset: int = self.font.size // 2 + top_padding
        self.label, self.label_rect = self.font.render(label, WHITE)
        self.label_rect.center = (self.width // 2, label_offset)

        self.surface = Surface((self.width, self.height), pygame.SRCALPHA)
        self.value_offset = label_offset + self.font.size

        self.graph_top = int(self.height * 0.5)
        self.graph_height = self.height - self.graph_top

        # Pre-render the background with label (never changes)
        self._background_surface = Surface((self.width, self.height), pygame.SRCALPHA)
        self._background_surface.fill((0, 0, 0, self.graph_alpha))
        self._background_surface.blit(self.label, self.label_rect)

        # Cache for rendered FPS text
        self._cached_smoothed_fps: int | None = None
        self._cached_fps_surface: Surface | None = None
        self._cached_fps_rect = None

        # Status icon state
        self._status_icon: Surface | None = None
        self._status_icon_padding = 2

    def set_status_icon(
        self,
        icon_name: str,
        color: Tuple[int, int, int] = (255, 255, 255)
    ) -> None:
        """Set a status icon to display in the bottom right corner.

        Args:
            icon_name: Material icon name to display.
            color: RGB color tuple for the icon.
        """
        icon_size = int((self.graph_height - self._status_icon_padding * 2) * 0.7)
        self._status_icon = get_icon(icon_name, size=icon_size, color=color)

    def clear_status_icon(self) -> None:
        self._status_icon = None

    def draw(self, screen: Surface, fps: float) -> None:
        self.history.append(fps)
        if len(self.history) < 2:
            return

        recent_fps = list(self.history)[-self.average_window:]
        average_fps = int(sum(recent_fps) // len(recent_fps)) if recent_fps else 0
        self.smoothed_fps.append(average_fps)
        smoothed_fps = int(sum(self.smoothed_fps) // len(self.smoothed_fps))

        # Clear surface and blit cached background
        self.surface.fill((0, 0, 0, 0))  # Fully transparent
        self.surface.blit(self._background_surface, (0, 0))

        # Only render FPS text if value changed
        if smoothed_fps != self._cached_smoothed_fps:
            fps_value, value_rect = self.font.render(f"{smoothed_fps:2d} FPS", WHITE)
            value_rect.center = (self.width // 2, self.value_offset)
            self._cached_fps_surface = fps_value
            self._cached_fps_rect = value_rect
            self._cached_smoothed_fps = smoothed_fps

        # Blit cached FPS text
        if self._cached_fps_surface is not None:
            self.surface.blit(self._cached_fps_surface, self._cached_fps_rect)

        # Draw graph (updated every frame)
        min_fps = 0
        max_fps = max(self.history)
        fps_range = max(max_fps - min_fps, 1)

        graph_points = []
        for i, fps in enumerate(self.history):
            x = int(i / self.graph_frames * self.width)
            y = int((1 - (fps - min_fps) / fps_range) * self.graph_height)
            graph_points.append((x, self.graph_top + y))

        if len(graph_points) >= 2:
            pygame.draw.lines(self.surface, GREEN, False, graph_points, 2)

        # Draw status icon in bottom right corner
        if self._status_icon is not None:
            icon_x = self.width - self._status_icon.get_width() - self._status_icon_padding
            icon_y = self.height - self._status_icon.get_height() - self._status_icon_padding
            self.surface.blit(self._status_icon, (icon_x, icon_y))

        rounded = round_corners(self.surface, 4)
        screen.blit(rounded, self.position)
