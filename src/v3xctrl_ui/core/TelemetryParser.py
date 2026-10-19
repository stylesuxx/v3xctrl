"""Telemetry message parser for extracting and formatting telemetry data."""

from dataclasses import dataclass, field

from v3xctrl_control.message import Telemetry
from v3xctrl_ui.core.dataclasses import GpsFixType


@dataclass
class TelemetryData:
    signal_quality: dict[str, int] = field(default_factory=lambda: {"rsrq": -1, "rsrp": -1})
    signal_band: str = "BAND ?"
    signal_cell: str = "CELL ?"
    battery_icon: int = 0
    battery_voltage: str = "0.00V"
    battery_average_voltage: str = "0.00V"
    battery_percent: str = "0%"
    battery_current: str = "0mA"
    battery_warning: bool = False
    gps_fix_type: GpsFixType = GpsFixType.NO_HARDWARE
    gps_speed: float = 0.0
    gps_satellites: str = "0 SAT"


def parse_telemetry(message: Telemetry) -> TelemetryData:
    data = TelemetryData()
    values = message.get_values()

    # Signal quality & band
    data.signal_quality = {
        "rsrq": values["sig"]["rsrq"],
        "rsrp": values["sig"]["rsrp"],
    }
    band = values["cell"]["band"]
    data.signal_band = f"BAND {band}"

    # Cell ID
    cell_id = values["cell"]["id"]
    cell_text = f"CELL {cell_id}"
    if cell_id != "?":
        tower_id = cell_id >> 8
        section_id = cell_id & 0xFF
        cell_text = f"{tower_id}:{section_id}"
    data.signal_cell = cell_text

    # Battery
    battery_voltage = values["bat"]["vol"] / 1000
    battery_average_voltage = values["bat"]["avg"] / 1000
    battery_percentage = values["bat"]["pct"]
    battery_current_ma = values["bat"].get("cur", 0)

    data.battery_icon = battery_percentage
    data.battery_voltage = f"{battery_voltage:.2f}V"
    data.battery_average_voltage = f"{battery_average_voltage:.2f}V"
    data.battery_percent = f"{battery_percentage}%"
    data.battery_warning = values["bat"]["wrn"]

    data.battery_current = f"{battery_current_ma}mA"
    if battery_current_ma >= 1000:
        data.battery_current = f"{battery_current_ma / 1000:.2f}A"

    # GPS
    loc = values.get("loc", {})
    data.gps_fix_type = GpsFixType(int(loc.get("fix_type", GpsFixType.NO_HARDWARE)))
    data.gps_speed = float(loc.get("speed", 0.0))
    data.gps_satellites = f"{loc.get('satellites', 0)} SAT"

    return data
