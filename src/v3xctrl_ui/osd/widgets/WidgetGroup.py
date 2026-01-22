"""Widget group abstraction for unified rendering."""
from dataclasses import dataclass
from typing import Dict, Callable, Any
from v3xctrl_ui.osd.widgets import Widget


@dataclass
class WidgetGroup:
    name: str
    widgets: Dict[str, Widget]
    get_value: Callable[[str], Any]
    use_composition: bool = True
    corner_radius: int = 4

    @classmethod
    def create(
        cls,
        name: str,
        widgets: Dict[str, Widget],
        get_value: Callable[[str], Any],
        use_composition: bool = True,
        corner_radius: int = 4
    ) -> 'WidgetGroup':
        """Create a widget group.

        Args:
            name: Settings key for this group (e.g., "battery", "debug")
            widgets: Dict of widget name to widget instance
            get_value: Callable to get attribute value by name
            use_composition: If True, compose widgets into single surface.
                           If False, render individually with separate positioning.
            corner_radius: Radius for rounded corners when using composition
        """
        return cls(name, widgets, get_value, use_composition, corner_radius)
