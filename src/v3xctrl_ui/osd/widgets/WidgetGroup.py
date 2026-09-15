"""Widget group abstraction for unified rendering."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from v3xctrl_ui.osd.widgets import Widget

ValueT = TypeVar("ValueT")


@dataclass(frozen=True, slots=True)
class WidgetEntry(Generic[ValueT]):
    """A widget, the settings key it is configured under, and where its value comes from.

    `get_value` is called once per rendered frame, for this widget alone.
    """

    name: str
    widget: Widget[ValueT]
    get_value: Callable[[], ValueT]


@dataclass(frozen=True, slots=True)
class WidgetGroup:
    """Widgets drawn together under one settings key.

    name: settings key for the group (e.g. "battery", "debug")
    entries: the widgets, in draw order
    use_composition: compose into a single surface, or position each widget on
        its own from its own config
    corner_radius: radius for the rounded corners of a composed group
    """

    name: str
    entries: tuple[WidgetEntry[Any], ...]
    use_composition: bool = True
    corner_radius: int = 4
