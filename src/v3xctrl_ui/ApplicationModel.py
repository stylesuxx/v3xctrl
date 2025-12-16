from dataclasses import dataclass, field
from collections import deque
from typing import Optional


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
    last_control_update: float = 0.0
    last_latency_check: float = 0.0

    # Lifecycle state
    running: bool = True
    menu_open: bool = False

    # Network restart state
    network_restart_pending: bool = False
    pending_settings: Optional['Settings'] = None
