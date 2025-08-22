import logging
import socket
import threading
import time
from typing import Dict, List, Set, Optional

from v3xctrl_helper import Address
from v3xctrl_udp_relay.custom_types import Role, PortType, PeerEntry


class PacketRelay:
    """
    The main goal of the packet relay is to quickly forward packages from one
    peer to the other.

    When traffic has not been seen for a certain amount of time, the relay will
    invalidate the mapping.

    Mappings are stored in a dictionary keyed by their source address. The
    value is a tuple containing the target address and the timestamp of the
    last time a message has been seen from the source address.
    """
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

        self.relay_map: Dict[Address, tuple[Address, float]] = {}
        self.session_to_addresses: Dict[str, Set[Address]] = {}
        self.address_to_session: Dict[Address, str] = {}

        self.lock = threading.Lock()

    def update_mapping(
        self,
        sid: str,
        peers: Dict[Role, Dict[PortType, PeerEntry]]
      ) -> None:
        streamer_peers = peers.get(Role.STREAMER, {})
        viewer_peers = peers.get(Role.VIEWER, {})

        if (
            len(streamer_peers) != len(PortType) or
            len(viewer_peers) != len(PortType)
        ):
            return

        now = time.time()
        new_mappings: Dict[Address, tuple[Address, float]] = {}
        session_addresses: Set[Address] = set()

        for port_type in PortType:
            if port_type in streamer_peers and port_type in viewer_peers:
                streamer_addr = streamer_peers[port_type].addr
                viewer_addr = viewer_peers[port_type].addr

                new_mappings[streamer_addr] = (viewer_addr, now)
                new_mappings[viewer_addr] = (streamer_addr, now)

                session_addresses.add(streamer_addr)
                session_addresses.add(viewer_addr)

        with self.lock:
            # Clean up old mappings for this session first
            old_addresses = self.session_to_addresses.get(sid, set())
            for addr in old_addresses:
                self.relay_map.pop(addr, None)
                self.address_to_session.pop(addr, None)

            # Update with new mappings
            self.relay_map.update(new_mappings)
            self.session_to_addresses[sid] = session_addresses

            for addr in session_addresses:
                self.address_to_session[addr] = sid

    def remove_session(self, sid: str) -> None:
        """Remove session and all it's mappings"""
        with self.lock:
            addresses = self.session_to_addresses.pop(sid, set())
            for addr in addresses:
                self.relay_map.pop(addr, None)
                self.address_to_session.pop(addr, None)

    def get_session_for_address(self, addr: Address) -> Optional[str]:
        with self.lock:
            return self.address_to_session.get(addr)

    def forward_packet(
        self,
        sock: socket.socket,
        data: bytes,
        addr: Address
    ) -> None:
        with self.lock:
            mapping = self.relay_map.get(addr)
            if not mapping:
                return

            target, _ = mapping
            self.relay_map[addr] = (target, time.time())

        sock.sendto(data, target)

    def cleanup_expired_mappings(self) -> Set[str]:
        """Returns set of expired session IDs"""
        now = time.time()

        with self.lock:
            expired_addresses: List[Address] = []
            for addr, (_, ts) in self.relay_map.items():
                if (now - ts) > self.timeout:
                    expired_addresses.append(addr)

            affected_sessions: Set[str] = set()
            for addr in expired_addresses:
                sid = self.address_to_session.get(addr)
                if sid:
                    affected_sessions.add(sid)
                    self.address_to_session.pop(addr, None)
                    del self.relay_map[addr]

                    logging.info(f"{sid}: Removed expired mapping for {addr}")

            # Check which sessions are completely expired
            fully_expired_sessions: Set[str] = set()
            for session_id in affected_sessions:
                session_addresses = self.session_to_addresses.get(session_id, set())
                has_active_mappings = any(addr in self.relay_map for addr in session_addresses)

                if not has_active_mappings:
                    # All mappings for this session are gone
                    fully_expired_sessions.add(session_id)
                    self.session_to_addresses.pop(session_id, None)

                else:
                    # Update session_to_addresses to only include active addresses
                    active_addresses = {addr for addr in session_addresses if addr in self.relay_map}
                    self.session_to_addresses[session_id] = active_addresses

        return fully_expired_sessions
