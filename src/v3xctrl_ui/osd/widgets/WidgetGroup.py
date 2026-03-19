"""Widget group abstraction for unified rendering."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from v3xctrl_ui.osd.widgets import Widget


@dataclass
class WidgetGroup:
    name: str
    widgets: dict[str, Widget]
    get_value: Callable[[str], Any]
    use_composition: bool = True
    corner_radius: int = 4
    settings_aliases: dict[str, str] = field(default_factory=dict)
    header_height: int = 0

    @classmethod
    def create(
        cls,
        name: str,
        widgets: dict[str, Widget],
        get_value: Callable[[str], Any],
        use_composition: bool = True,
        corner_radius: int = 4,
        settings_aliases: dict[str, str] | None = None,
        header_height: int = 0,
    ) -> "WidgetGroup":
        """Create a widget group.

        Args:
            name: Settings key for this group (e.g., "battery", "debug")
            widgets: Dict of widget name to widget instance
            get_value: Callable to get attribute value by name
            use_composition: If True, compose widgets into single surface.
                           If False, render individually with separate positioning.
            corner_radius: Radius for rounded corners when using composition
            settings_aliases: Maps widget names to a different settings key,
                              e.g. {"gps_fix": "gps_details"} makes gps_fix
                              visible when the gps_details setting is enabled.
        """
        return cls(name, widgets, get_value, use_composition, corner_radius, settings_aliases or {}, header_height)
