"""Widget group abstraction for unified rendering."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from v3xctrl_ui.osd.widgets import Widget


@dataclass
class WidgetGroup:
    name: str
    widgets: dict[str, Widget]
    get_value: Callable[[str], Any]
    use_composition: bool = True
    corner_radius: int = 4

    @classmethod
    def create(
        cls,
        name: str,
        widgets: dict[str, Widget],
        get_value: Callable[[str], Any],
        use_composition: bool = True,
        corner_radius: int = 4,
    ) -> "WidgetGroup":
        return cls(name, widgets, get_value, use_composition, corner_radius)
