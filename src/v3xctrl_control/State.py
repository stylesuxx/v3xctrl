from enum import Enum


class State(Enum):
    WAITING = "waiting"
    SPECTATING = "spectating"
    CONNECTED = "connected"
    # No message within the failsafe timeout: outputs are neutral, the session stays up
    FAILSAFE = "failsafe"
    DISCONNECTED = "disconnected"
