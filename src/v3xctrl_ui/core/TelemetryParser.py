"""Telemetry message parser for extracting and formatting telemetry data."""

from dataclasses import dataclass, field

from v3xctrl_control.message import Telemetry


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
    gps_fix_type: int = -1
    gps_speed: str = "0 km/h"
    gps_satellites: str = "0 SAT"
    recording: bool = False
    service_video: bool = False
    service_debug: bool = False
    vc_current_flags: int = 0
    vc_history_flags: int = 0


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
    data.gps_fix_type = int(loc.get("fix_type", -1))
    data.gps_speed = f"{int(loc.get('speed', 0.0))} km/h"
    data.gps_satellites = f"{loc.get('satellites', 0)} SAT"

    # GStreamer - bit 0 = recording
    gst = values.get("gst", 0)
    data.recording = bool(gst & (1 << 0))

    # Services - bit 0 = video, bit 1 = debug
    services = values.get("svc", 0)
    data.service_video = bool(services & (1 << 0))
    data.service_debug = bool(services & (1 << 1))

    # VideoCore - bits 0-3 = current, bits 4-7 = history
    video_core = values.get("vc", 0)
    data.vc_current_flags = video_core & 0x0F
    data.vc_history_flags = (video_core >> 4) & 0x0F

    return data
