import time
from enum import Enum

from v3xctrl_helper import Address
from v3xctrl_relay.Role import Role
from v3xctrl_tcp import Transport


class PortType(Enum):
    VIDEO = "video"
    CONTROL = "control"


class PeerEntry:
    def __init__(self, addr: Address, transport: Transport = Transport.UDP) -> None:
        self.addr = addr
        self.transport = transport
        self.ts = time.time()


class SpectatorEntry:
    """Entry for a spectator peer with multiple port addresses.

    Spectators are grouped by source IP. This means only one spectator per
    public IP address is supported per session.
    """

    def __init__(self) -> None:
        self.ports: dict[PortType, PeerEntry] = {}
        self.created_at: float = time.time()
        self.last_announcement_at: float = time.time()

    def register_port(
        self, port_type: PortType, addr: Address, transport: Transport = Transport.UDP
    ) -> tuple[bool, Address | None]:
        old_entry = self.ports.get(port_type)
        replaced_addr = old_entry.addr if old_entry and old_entry.addr != addr else None
        new_port = old_entry is None
        self.ports[port_type] = PeerEntry(addr, transport)
        self.last_announcement_at = time.time()
        return (new_port, replaced_addr)

    def is_complete(self) -> bool:
        return len(self.ports) == len(PortType)

    def get_addresses(self) -> set[Address]:
        return {peer.addr for peer in self.ports.values()}


class Session:
    def __init__(self, session_id: str) -> None:
        self.id = session_id
        self.roles: dict[Role, dict[PortType, PeerEntry]] = {Role.STREAMER: {}, Role.VIEWER: {}}
        self.spectators: list[SpectatorEntry] = []
        self.addresses: set[Address] = set()
        self.created_at: float = time.time()
        self.last_announcement_at: float = time.time()

    def register(
        self, role: Role, port_type: PortType, addr: Address, transport: Transport = Transport.UDP
    ) -> tuple[bool, Address | None]:
        if role == Role.SPECTATOR:
            return self._register_spectator(port_type, addr, transport)
        elif role == Role.STREAMER or role == Role.VIEWER:
            return (self._register_peer(role, port_type, addr, transport), None)

        raise ValueError(f"Unknown role: {role}")

    def _register_peer(self, role: Role, port_type: PortType, addr: Address, transport: Transport) -> bool:
        new_peer = port_type not in self.roles[role]
        self.roles[role][port_type] = PeerEntry(addr, transport)
        self.addresses.add(addr)
        self.last_announcement_at = time.time()

        return new_peer

    def _register_spectator(
        self, port_type: PortType, addr: Address, transport: Transport
    ) -> tuple[bool, Address | None]:
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
        new_port, replaced_addr = spectator.register_port(port_type, addr, transport)
        if replaced_addr:
            self.addresses.discard(replaced_addr)
        return (new_port, replaced_addr)

    def remove_spectator_by_address(self, addr: Address) -> set[Address] | None:
        for i, spectator in enumerate(self.spectators):
            if addr in spectator.get_addresses():
                spectator_addresses = spectator.get_addresses().copy()

                for spectator_addr in spectator_addresses:
                    self.addresses.discard(spectator_addr)

                self.spectators.pop(i)
                return spectator_addresses

        return None

    def find_spectator_by_address(self, addr: Address) -> SpectatorEntry | None:
        for spectator in self.spectators:
            if addr in spectator.get_addresses():
                return spectator

        return None

    def is_role_ready(self, role: Role) -> bool:
        return all(port_type in self.roles[role] for port_type in PortType)

    def is_ready(self) -> bool:
        return self.is_role_ready(Role.STREAMER) and self.is_role_ready(Role.VIEWER)


class SessionNotFoundError(Exception):
    pass
