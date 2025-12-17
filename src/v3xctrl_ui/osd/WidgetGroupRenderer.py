"""Renderer for composing and drawing widget groups."""
from typing import Dict, Any, List, Tuple, ItemsView, Callable
import pygame
from v3xctrl_ui.utils.helpers import calculate_widget_position, round_corners
from v3xctrl_ui.osd.widgets import Widget


class WidgetGroupRenderer:
    @staticmethod
    def render_group(
        screen: pygame.Surface,
        widgets: ItemsView[str, Widget],
        settings: Dict[str, Any],
        widget_settings: Dict[str, Dict[str, Any]],
        get_widget_value: Callable[[str], Any],
        corner_radius: int = 4
    ) -> None:
        if not settings.get("display", False):
            return

        align = settings.get("align", "top-left")
        offset = settings.get("offset", (0, 0))
        padding = settings.get("padding", 0)

        visible_widgets = WidgetGroupRenderer._filter_visible_widgets(
            widgets, widget_settings
        )

        if not visible_widgets:
            return

        width, height = WidgetGroupRenderer._calculate_dimensions(
            visible_widgets, padding
        )

        composed = pygame.Surface((width, height), pygame.SRCALPHA)

        WidgetGroupRenderer._draw_widgets_to_surface(
            composed, visible_widgets, get_widget_value, padding
        )

        screen_width, screen_height = pygame.display.get_window_size()
        position = calculate_widget_position(
            align, composed.get_width(), composed.get_height(),
            screen_width, screen_height, offset
        )

        rounded = round_corners(composed, corner_radius)
        screen.blit(rounded, position)

    @staticmethod
    def _filter_visible_widgets(
        widgets: ItemsView[str, Widget],
        widget_settings: Dict[str, Dict[str, Any]]
    ) -> List[Tuple[str, Widget]]:
        visible = []
        for name, widget in widgets:
            settings = widget_settings.get(name, {})
            if settings.get("display", True):
                visible.append((name, widget))

        return visible

    @staticmethod
    def _calculate_dimensions(
        widgets: List[Tuple[str, Widget]],
        padding: int
    ) -> Tuple[int, int]:
        width = 0
        height = 0

        for _, widget in widgets:
            width = max(width, widget.width)
            height += widget.height + padding

        if height > 0:
            height -= padding

        return width, height

    @staticmethod
    def _draw_widgets_to_surface(
        surface: pygame.Surface,
        widgets: List[Tuple[str, Widget]],
        get_widget_value: Callable[[str], Any],
        padding: int
    ) -> None:
        """Draw all widgets to the composed surface."""
        y_offset = 0
        for name, widget in widgets:
            widget.position = (0, y_offset)
            widget.draw(surface, get_widget_value(name))
            y_offset += widget.height + padding
