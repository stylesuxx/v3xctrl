from dataclasses import dataclass, field
from collections import deque
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from v3xctrl_ui.utils.Settings import Settings


@dataclass
class ApplicationModel:
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
