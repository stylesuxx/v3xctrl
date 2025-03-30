import pygame
from pygame import Surface
from typing import Tuple

from ui.widgets.Widget import Widget
from ui.colors import WHITE, GREEN


class FpsWidget(Widget):
    def __init__(self, screen: Surface, position: Tuple[int, int], size: Tuple[int, int], label: str):
        super().__init__()

        self.screen = screen

        self.position = position

        self.size = size
        self.width = self.size[0]
        self.height = self.size[1]

        self.label = label

        self.graph_alpha = 180
        self.average_window = 30
        self.graph_frames = 300

    def draw(self, history) -> Surface:
        if len(history) < 2:
            return

        top_padding = 2
        font_size = 16
        font = pygame.font.SysFont("monospace", font_size, bold=True)

        widget_surface = Surface((self.width, self.height), pygame.SRCALPHA)
        widget_surface.fill((0, 0, 0, self.graph_alpha))

        recent_fps = list(history)[-self.average_window:]
        average_fps = sum(recent_fps) / len(recent_fps)

        # Draw label in top half
        label_offset = font_size / 2 + top_padding
        fps_label = font.render(self.label, True, WHITE)
        label_rect = fps_label.get_rect(center=(self.width // 2, label_offset))
        widget_surface.blit(fps_label, label_rect)

        value_offset = label_offset + font_size
        fps_value = font.render(f"{average_fps:.1f} FPS", True, WHITE)
        value_rect = fps_value.get_rect(center=(self.width // 2, value_offset))
        widget_surface.blit(fps_value, value_rect)

        # Graph in bottom half
        max_fps = max(history)
        min_fps = 0
        fps_range = max(max_fps - min_fps, 1)

        graph_points = []
        for i, fps in enumerate(history):
            x = int(i / self.graph_frames * self.width)
            y = int((1 - (fps - min_fps) / fps_range) * self.height // 2)
            graph_points.append((x, self.height // 2 + y))

        if len(graph_points) >= 2:
            pygame.draw.lines(widget_surface, GREEN, False, graph_points, 2)

        self.screen.blit(widget_surface, self.position)
