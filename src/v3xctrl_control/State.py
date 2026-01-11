from enum import Enum


class State(Enum):
    WAITING = "waiting"
    SPECTATING = "spectating"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
