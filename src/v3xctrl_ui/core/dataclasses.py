"""Core dataclasses for v3xctrl_ui."""
from dataclasses import dataclass, field
from collections import deque
from typing import Dict, Optional, TYPE_CHECKING

# Re-export telemetry dataclasses for backwards compatibility
from v3xctrl_telemetry import (
    ServiceFlags,
    GstFlags,
    VideoCoreFlags,
    ThrottleFlags,
)

if TYPE_CHECKING:
    from v3xctrl_ui.core.Settings import Settings


@dataclass
class ApplicationModel:
    """Application state model."""
    # Control
    throttle: float = 0.0
    steering: float = 0.0
    control_connected: bool = False

    # Display
    fullscreen: bool = False
    scale: float = 1.0

    # Timing
    loop_history: deque[float] = field(default_factory=lambda: deque(maxlen=300))
    control_interval: float = 0.0
    latency_interval: float = 0.0
    last_control_update: float = 0.0
    last_latency_check: float = 0.0

    # Lifecycle
    running: bool = True

    # Network
    pending_settings: Optional['Settings'] = None


@dataclass
class BatteryData:
    """Battery telemetry data."""
    icon: int = 0
    voltage: str = "0.00V"
    average_voltage: str = "0.00V"
    percent: str = "0%"
    warning: bool = False


@dataclass
class SignalData:
    """Signal telemetry data."""
    quality: Dict[str, int] = field(default_factory=lambda: {"rsrq": -1, "rsrp": -1})
    band: str = "BAND ?"
    cell: str = "CELL ?"
