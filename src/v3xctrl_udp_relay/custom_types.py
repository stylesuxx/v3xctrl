from enum import Enum
import time
from typing import Dict, Set

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
    def __init__(self, id: str) -> None:
        self.id = id
        self.roles: Dict[Role, Dict[PortType, PeerEntry]] = {
            Role.STREAMER: {},
            Role.VIEWER: {}
        }
        self.addresses: Set[Address] = set()
        self.created_at: float = time.time()
        self.last_announcement_at: float = time.time()

    def register(self, role: Role, port_type: PortType, addr: Address) -> bool:
        """Returns true if it is a new peer."""
        new_peer = port_type not in self.roles[role]
        self.roles[role][port_type] = PeerEntry(addr)
        self.addresses.add(addr)
        self.last_announcement_at = time.time()

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


class SessionNotFoundError(Exception):
    pass
