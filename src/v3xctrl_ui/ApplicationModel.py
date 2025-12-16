from dataclasses import dataclass, field
from collections import deque
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from v3xctrl_ui.Settings import Settings


@dataclass
class ApplicationModel:
    """Pure state - no behavior, just data."""

    # Control state
    throttle: float = 0.0
    steering: float = 0.0
    control_connected: bool = False

    # Display state
    fullscreen: bool = False
    scale: float = 1.0

    # Timing state
    loop_history: deque[float] = field(default_factory=lambda: deque(maxlen=300))
    control_interval: float = 0.0
    latency_interval: float = 0.0
    last_control_update: float = 0.0
    last_latency_check: float = 0.0

    # Lifecycle state
    running: bool = True

    # Network restart state
    pending_settings: Optional['Settings'] = None
