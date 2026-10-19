from collections.abc import Sequence
from typing import Any

import pygame

from v3xctrl_ui.core.SettingsSchema import WidgetConfig, WidgetSettings
from v3xctrl_ui.osd.widgets.WidgetGroup import WidgetEntry, WidgetGroup
from v3xctrl_ui.utils.helpers import calculate_widget_position, round_corners


def render_widget_group(screen: pygame.Surface, group: WidgetGroup, widget_settings: WidgetSettings) -> None:
    """
    Render a widget group using either composition or individual rendering.

    Args:
        screen: Surface to render onto
        group: WidgetGroup to render
        widget_settings: Configuration for every widget and group
    """
    if group.use_composition:
        render_group(
            screen,
            group.entries,
            widget_settings.get(group.name) or WidgetConfig(),
            widget_settings,
            group.corner_radius,
        )
    else:
        _render_individual_widgets(screen, group.entries, widget_settings)


def render_group(
    screen: pygame.Surface,
    entries: Sequence[WidgetEntry[Any]],
    config: WidgetConfig,
    widget_settings: WidgetSettings,
    corner_radius: int = 4,
) -> None:
    """Render widgets as a composed group with rounded corners."""
    if not config.display:
        return

    visible_entries = _filter_visible_entries(entries, widget_settings)
    if not visible_entries:
        return

    align = config.align
    offset = config.offset
    padding = config.padding
    width, height = _calculate_dimensions(visible_entries, padding)

    composed = pygame.Surface((width, height), pygame.SRCALPHA)
    _draw_entries_to_surface(composed, visible_entries, padding)

    screen_width, screen_height = screen.get_size()
    position = calculate_widget_position(align, width, height, screen_width, screen_height, offset)
    blit_surface = round_corners(composed, corner_radius)

    screen.blit(blit_surface, position)


def _render_individual_widgets(
    screen: pygame.Surface,
    entries: Sequence[WidgetEntry[Any]],
    widget_settings: WidgetSettings,
) -> None:
    for entry in entries:
        # A widget drawn on its own stays hidden unless the config names it
        config = widget_settings.get(entry.name)

        if config is not None and config.display:
            widget = entry.widget
            screen_width, screen_height = screen.get_size()
            position = calculate_widget_position(
                config.align, widget.width, widget.height, screen_width, screen_height, config.offset
            )

            widget.position = position
            widget.draw(screen, entry.get_value())


def _filter_visible_entries(
    entries: Sequence[WidgetEntry[Any]],
    widget_settings: WidgetSettings,
) -> list[WidgetEntry[Any]]:
    visible: list[WidgetEntry[Any]] = []
    for entry in entries:
        # A widget inside a group is drawn unless the config hides it, which is
        # what keeps widgets the config file never names (debug_buffer) visible
        config = widget_settings.get(entry.name)
        if config is None or config.display:
            visible.append(entry)

    return visible


def _calculate_dimensions(entries: Sequence[WidgetEntry[Any]], padding: int) -> tuple[int, int]:
    width = 0
    height = 0

    for entry in entries:
        width = max(width, entry.widget.width)
        height += entry.widget.height + padding

    if height > 0:
        height -= padding

    return width, height


def _draw_entries_to_surface(surface: pygame.Surface, entries: Sequence[WidgetEntry[Any]], padding: int) -> None:
    y_offset = 0
    for entry in entries:
        entry.widget.position = (0, y_offset)
        entry.widget.draw(surface, entry.get_value())
        y_offset += entry.widget.height + padding
