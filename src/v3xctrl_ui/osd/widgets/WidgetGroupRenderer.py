from typing import Dict, Any, List, Tuple, ItemsView, Callable
import pygame

from v3xctrl_ui.utils.helpers import calculate_widget_position, round_corners

from v3xctrl_ui.osd.widgets import Widget
from v3xctrl_ui.osd.widgets.WidgetGroup import WidgetGroup


def render_widget_group(
    screen: pygame.Surface,
    group: WidgetGroup,
    widget_settings: Dict[str, Dict[str, Any]]
) -> None:
    """
    Render a widget group using either composition or individual rendering.

    Args:
        screen: Surface to render onto
        group: WidgetGroup to render
        widget_settings: Global widget settings dict
    """
    settings = widget_settings.get(group.name, {})

    if group.use_composition:
        render_group(
            screen,
            group.widgets.items(),
            settings,
            widget_settings,
            group.get_value,
            group.corner_radius
        )
    else:
        _render_individual_widgets(
            screen,
            group.widgets.items(),
            widget_settings,
            group.get_value
        )


def render_group(
    screen: pygame.Surface,
    widgets: ItemsView[str, Widget],
    settings: Dict[str, Any],
    widget_settings: Dict[str, Dict[str, Any]],
    get_widget_value: Callable[[str], Any],
    corner_radius: int = 4
) -> None:
    """Render widgets as a composed group with rounded corners."""
    if not settings.get("display", False):
        return

    visible_widgets = _filter_visible_widgets(widgets, widget_settings)
    if not visible_widgets:
        return

    align = settings.get("align", "top-left")
    offset = settings.get("offset", (0, 0))
    padding = settings.get("padding", 0)
    width, height = _calculate_dimensions(visible_widgets, padding)

    composed = pygame.Surface((width, height), pygame.SRCALPHA)

    _draw_widgets_to_surface(
        composed, visible_widgets, get_widget_value, padding
    )

    screen_width, screen_height = pygame.display.get_window_size()
    position = calculate_widget_position(
        align, composed.get_width(), composed.get_height(),
        screen_width, screen_height, offset
    )

    rounded = round_corners(composed, corner_radius)
    screen.blit(rounded, position)


def _render_individual_widgets(
    screen: pygame.Surface,
    widgets: ItemsView[str, Widget],
    widget_settings: Dict[str, Dict[str, Any]],
    get_widget_value: Callable[[str], Any]
) -> None:
    for name, widget in widgets:
        settings = widget_settings.get(name, {
            "align": "top-left",
            "offset": (0, 0),
            "display": False
        })

        if settings.get("display", False):
            align = settings.get("align", "top-left")
            offset = settings.get("offset", (0, 0))
            screen_width, screen_height = pygame.display.get_window_size()
            position = calculate_widget_position(
                align, widget.width, widget.height,
                screen_width, screen_height, offset
            )

            widget.position = position
            widget.draw(screen, get_widget_value(name))


def _filter_visible_widgets(
    widgets: ItemsView[str, Widget],
    widget_settings: Dict[str, Dict[str, Any]]
) -> List[Tuple[str, Widget]]:
    visible: List[Tuple[str, Widget]] = []
    for name, widget in widgets:
        settings = widget_settings.get(name, {})
        if settings.get("display", True):
            visible.append((name, widget))

    return visible


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


def _draw_widgets_to_surface(
    surface: pygame.Surface,
    widgets: List[Tuple[str, Widget]],
    get_widget_value: Callable[[str], Any],
    padding: int
) -> None:
    y_offset = 0
    for name, widget in widgets:
        widget.position = (0, y_offset)
        widget.draw(surface, get_widget_value(name))
        y_offset += widget.height + padding
