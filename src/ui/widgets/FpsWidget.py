from collections import deque
import pygame
from pygame import Surface
from typing import Tuple

from ui.widgets.Widget import Widget
from ui.colors import WHITE, GREEN


class FpsWidget(Widget):
    def __init__(self, position: Tuple[int, int], size: Tuple[int, int], label: str):
        super().__init__()

        self.position = position

        self.size = size
        self.width, self.height = self.size

        self.graph_alpha = 180

        self.average_window = 1
        self.graph_frames = 300
        self.history = deque(maxlen=self.graph_frames)

        font_size = 16
        self.font = pygame.font.SysFont("monospace", font_size, bold=True)

        top_padding = 2
        label_offset = font_size / 2 + top_padding
        self.label = self.font.render(label, True, WHITE)
        self.label_rect = self.label.get_rect(center=(self.width // 2, label_offset))

        self.surface = Surface((self.width, self.height), pygame.SRCALPHA)
        self.value_offset = label_offset + font_size

        self.graph_top = int(self.height * 0.5)
        self.graph_height = self.height - self.graph_top

    def draw(self, screen: Surface, fps: float) -> None:
        self.history.append(fps)
        if len(self.history) < 2:
            return

        recent_fps = list(self.history)[-self.average_window:]
        average_fps = round(sum(recent_fps) / len(recent_fps), 1) if recent_fps else 0.0

        min_fps = 0
        max_fps = max(self.history)
        fps_range = max(max_fps - min_fps, 1)

        self.surface.fill((0, 0, 0, self.graph_alpha))

        # Draw label in top half
        self.surface.blit(self.label, self.label_rect)

        fps_value = self.font.render(f"{average_fps:.1f} FPS", True, WHITE)
        value_rect = fps_value.get_rect(center=(self.width // 2, self.value_offset))
        self.surface.blit(fps_value, value_rect)

        # Graph in bottom half
        graph_points = []
        for i, fps in enumerate(self.history):
            x = int(i / self.graph_frames * self.width)
            y = int((1 - (fps - min_fps) / fps_range) * self.graph_height)
            graph_points.append((x, self.graph_top + y))

        if len(graph_points) >= 2:
            pygame.draw.lines(self.surface, GREEN, False, graph_points, 2)

        screen.blit(self.surface, self.position)
