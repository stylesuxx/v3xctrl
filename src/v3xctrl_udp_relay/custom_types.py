from dataclasses import dataclass
from enum import Enum
import time
from typing import Dict, Optional

from v3xctrl_helper import Address


class Role(Enum):
    STREAMER = "streamer"
    VIEWER = "viewer"


class PortType(Enum):
    VIDEO = "video"
    CONTROL = "control"


class PeerEntry:
    def __init__(self, addr: Address) -> None:
        self.addr = addr
        self.ts = time.time()


class Session:
    def __init__(self) -> None:
        self.roles: Dict[Role, Dict[PortType, PeerEntry]] = {
            Role.STREAMER: {},
            Role.VIEWER: {}
        }
        self.created_at: float = time.time()

    def register(self, role: Role, port_type: PortType, addr: Address) -> bool:
        """Returns true if it is a new peer."""
        new_peer = port_type not in self.roles[role]
        self.roles[role][port_type] = PeerEntry(addr)

        return new_peer

    def is_role_ready(self, role: Role) -> bool:
        for port_type in PortType:
            if port_type not in self.roles[role]:
                return False

        return True

    def is_ready(self) -> bool:
        return (
            self.is_role_ready(Role.STREAMER) and
            self.is_role_ready(Role.VIEWER)
        )

    def get_peer(self, role: Role, port_type: PortType) -> Optional[PeerEntry]:
        return self.roles[role].get(port_type)


@dataclass
class RegistrationResult:
    error: Optional[Exception] = None
    is_new_peer: bool = False
    session_ready: bool = False


class SessionNotFoundError(Exception):
    pass
