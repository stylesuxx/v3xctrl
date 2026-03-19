from collections.abc import Callable, ItemsView
from typing import Any

import pygame

from v3xctrl_ui.osd.widgets import Widget
from v3xctrl_ui.osd.widgets.WidgetGroup import WidgetGroup
from v3xctrl_ui.utils.helpers import calculate_widget_position, round_corners


def render_widget_group(screen: pygame.Surface, group: WidgetGroup, widget_settings: dict[str, dict[str, Any]]) -> None:
    """
    Render a widget group using either composition or individual rendering.

    Args:
        screen: Surface to render onto
        group: WidgetGroup to render
        widget_settings: Global widget settings dict
    """
    settings = widget_settings.get(group.name, {})

    if group.use_composition:
        render_group(screen, group.widgets.items(), settings, widget_settings, group.get_value, group.corner_radius, group.settings_aliases)
    else:
        _render_individual_widgets(screen, group.widgets.items(), widget_settings, group.get_value, group.settings_aliases)


def render_group(
    screen: pygame.Surface,
    widgets: ItemsView[str, Widget],
    settings: dict[str, Any],
    widget_settings: dict[str, dict[str, Any]],
    get_widget_value: Callable[[str], Any],
    corner_radius: int = 4,
    settings_aliases: dict[str, str] | None = None,
) -> None:
    """Render widgets as a composed group with rounded corners."""
    if not settings.get("display", False):
        return

    visible_widgets = _filter_visible_widgets(widgets, widget_settings, settings_aliases or {})
    if not visible_widgets:
        return

    align = settings.get("align", "top-left")
    offset = settings.get("offset", (0, 0))
    padding = settings.get("padding", 0)
    width, height = _calculate_dimensions(visible_widgets, padding)

    composed = pygame.Surface((width, height), pygame.SRCALPHA)

    _draw_widgets_to_surface(composed, visible_widgets, get_widget_value, padding)

    screen_width, screen_height = screen.get_size()
    position = calculate_widget_position(
        align, composed.get_width(), composed.get_height(), screen_width, screen_height, offset
    )

    rounded = round_corners(composed, corner_radius)
    screen.blit(rounded, position)


def _render_individual_widgets(
    screen: pygame.Surface,
    widgets: ItemsView[str, Widget],
    widget_settings: dict[str, dict[str, Any]],
    get_widget_value: Callable[[str], Any],
    settings_aliases: dict[str, str] | None = None,
) -> None:
    aliases = settings_aliases or {}
    for name, widget in widgets:
        settings_key = aliases.get(name, name)
        settings = widget_settings.get(settings_key, {"align": "top-left", "offset": (0, 0), "display": False})

        if settings.get("display", False):
            align = settings.get("align", "top-left")
            offset = settings.get("offset", (0, 0))
            screen_width, screen_height = screen.get_size()
            position = calculate_widget_position(
                align, widget.width, widget.height, screen_width, screen_height, offset
            )

            widget.position = position
            widget.draw(screen, get_widget_value(name))


def _filter_visible_widgets(
    widgets: ItemsView[str, Widget],
    widget_settings: dict[str, dict[str, Any]],
    settings_aliases: dict[str, str] | None = None,
) -> list[tuple[str, Widget]]:
    aliases = settings_aliases or {}
    visible: list[tuple[str, Widget]] = []
    for name, widget in widgets:
        settings_key = aliases.get(name, name)
        settings = widget_settings.get(settings_key, {})
        if settings.get("display", True):
            visible.append((name, widget))

    return visible


def _calculate_dimensions(widgets: list[tuple[str, Widget]], padding: int) -> tuple[int, int]:
    width = 0
    height = 0

    for _, widget in widgets:
        width = max(width, widget.width)
        height += widget.height + padding

    if height > 0:
        height -= padding

    return width, height


def _draw_widgets_to_surface(
    surface: pygame.Surface, widgets: list[tuple[str, Widget]], get_widget_value: Callable[[str], Any], padding: int
) -> None:
    y_offset = 0
    for name, widget in widgets:
        widget.position = (0, y_offset)
        widget.draw(surface, get_widget_value(name))
        y_offset += widget.height + padding
