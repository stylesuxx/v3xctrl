"""Immutable per-frame data handed from the application loop to the Renderer."""

from collections import deque
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True, slots=True)
class ConnectionStatus:
    """State of the control and video channels for one frame."""

    user_connected: bool = False
    control_connected: bool = False
    control_error: str | None = None

    relay_enabled: bool = False
    relay_status_message: str = ""
    spectator: bool = False

    control_queue_depth: int = 0
    video_buffer_depth: int = 0


@dataclass(frozen=True, slots=True)
class FrameSnapshot:
    """Everything the Renderer needs to draw one frame.

    Holds references, never copies. The video frame is the array the receiver
    returned, so the Renderer's identity check can still skip a redundant blit,
    and a 1280x720 copy stays out of the frame budget. The histories are already
    copied by their owners, which is what makes them safe to read here while the
    receiver thread keeps appending.
    """

    connection: ConnectionStatus = field(default_factory=ConnectionStatus)
    video_frame: npt.NDArray[np.uint8] | None = None

    throttle: float = 0.0
    steering: float = 0.0

    menu_visible: bool = False
    fullscreen: bool = False
    scale: float = 1.0

    loop_history: deque[float] = field(default_factory=deque)
    video_history: deque[float] | None = None
