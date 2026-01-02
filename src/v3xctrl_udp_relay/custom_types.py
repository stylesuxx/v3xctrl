from enum import Enum
import time
from typing import Dict, Set, List

from v3xctrl_helper import Address
from v3xctrl_udp_relay.Role import Role


class PortType(Enum):
    VIDEO = "video"
    CONTROL = "control"


class PeerEntry:
    def __init__(self, addr: Address) -> None:
        self.addr = addr
        self.ts = time.time()


class SpectatorEntry:
    """Entry for a spectator peer with multiple port addresses."""
    def __init__(self) -> None:
        self.ports: Dict[PortType, PeerEntry] = {}
        self.created_at: float = time.time()

    def register_port(self, port_type: PortType, addr: Address) -> bool:
        new_port = port_type not in self.ports
        self.ports[port_type] = PeerEntry(addr)
        return new_port

    def is_complete(self) -> bool:
        return len(self.ports) == len(PortType)

    def get_addresses(self) -> Set[Address]:
        return {peer.addr for peer in self.ports.values()}


class Session:
    def __init__(self, id: str) -> None:
        self.id = id
        self.roles: Dict[Role, Dict[PortType, PeerEntry]] = {
            Role.STREAMER: {},
            Role.VIEWER: {}
        }
        self.spectators: List[SpectatorEntry] = []
        self.addresses: Set[Address] = set()
        self.created_at: float = time.time()
        self.last_announcement_at: float = time.time()

    def register(self, role: Role, port_type: PortType, addr: Address) -> bool:
        if role == Role.SPECTATOR:
            return self._register_spectator(port_type, addr)
        elif role == Role.STREAMER or role == Role.VIEWER:
            return self._register_peer(role, port_type, addr)

        raise ValueError(f'Unknown role: {role}')

    def _register_peer(self, role: Role, port_type: PortType, addr: Address) -> bool:
        new_peer = port_type not in self.roles[role]
        self.roles[role][port_type] = PeerEntry(addr)
        self.addresses.add(addr)
        self.last_announcement_at = time.time()

        return new_peer

    def _register_spectator(self, port_type: PortType, addr: Address) -> bool:
        ip = addr[0]
        spectator = None
        for spec in self.spectators:
            for peer in spec.ports.values():
                if peer.addr[0] == ip:
                    spectator = spec
                    break

            if spectator:
                break

        if not spectator:
            spectator = SpectatorEntry()
            self.spectators.append(spectator)

        self.addresses.add(addr)
        return spectator.register_port(port_type, addr)

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
