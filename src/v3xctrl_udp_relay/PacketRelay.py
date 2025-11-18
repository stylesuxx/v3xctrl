import logging
import socket
import threading
import time
from typing import Dict, List, Set

from v3xctrl_helper import Address
from v3xctrl_control.message import (
    Error,
    PeerInfo,
    PeerAnnouncement
)
from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.custom_types import (
    Role,
    PortType,
    Session,
    PeerEntry,
)


class PacketRelay:
    """
    Packet relay and session management.

    We have a couple of data structures that need to be kept in sync with each
    other, which makes this class a bit complicated:

    - mappings: This dict is used to quickly get a target address for a given
                source address - access in O(1)

    - sessions: A dict keyed by session IDs to keep track of all active
                sessions. Sessions are used to pair up viewer and streamer.
                Once a session has seen both, viewer and streamer it is
                considered to be complete and the mapping is added to the
                mappings.

    Sessions are cleaned up regularly and will be removed for one of the
    following reasons:

    - Orphaned: Session never became ready, initializing peer stopped sending
                data.

    - Expired:  Session became ready but all involved parties stopped sending
                data on all ports.

    - Overwrite:When a new session is ready, it is checked if other sessions
                using the same addresses are available, if so, those sessions
                are removed - this might happen if session ID is renewed and
                the previous session has not been removed in the meantime due to
                being orphaned or being expired.
    """

    def __init__(
        self,
        store: SessionStore,
        sock: socket.socket,
        address: Address,
        timeout: float
    ) -> None:
        self.store = store
        self.sock = sock
        self.ip = address[0]
        self.port = address[1]
        self.timeout = timeout

        self.mappings: Dict[Address, tuple[Address, float]] = {}
        self.sessions: Dict[str, Session] = {}

        # General lock, when execution is not hot path
        self.lock = threading.Lock()

        # Only lock mappings when absolutely necessary
        self.mapping_lock = threading.Lock()

    def register_peer(
        self,
        msg: PeerAnnouncement,
        addr: Address
    ) -> None:
        """Register a peer and automatically update relay mappings when session is ready."""
        try:
            role = Role(msg.get_role())
            port_type = PortType(msg.get_port_type())
        except ValueError:
            return

        sid = msg.get_id()

        with self.lock:
            if not self.store.exists(sid):
                logging.info(f"Ignoring announcement for unknown session '{sid}' from {addr}")
                try:
                    error_msg = Error(str(403))
                    self.sock.sendto(error_msg.to_bytes(), addr)
                except Exception as e:
                    logging.error(f"Failed to send error message to {addr}: {e}", exc_info=True)

                return

            session = self.sessions.setdefault(sid, Session(sid))
            is_new_peer = session.register(role, port_type, addr)

            if is_new_peer:
                logging.info(f"{sid}: Registered {role.name}:{port_type.name} from {addr}")

            if session.is_ready():
                self._update_mappings(session)
                self._send_peer_info(session)

                logging.info(f"{sid}: Session ready, peer info exchanged")

    def get_session_peers(self, sid: str) -> Dict[Role, Dict[PortType, PeerEntry]]:
        """Get all peers for a session."""
        with self.lock:
            session = self.sessions.get(sid)
            if not session:
                return {}

            return session.roles

    def forward_packet(
        self,
        data: bytes,
        addr: Address
    ) -> None:
        with self.mapping_lock:
            mapping = self.mappings.get(addr)
            if not mapping:
                return

            target, _ = mapping
            self.mappings[addr] = (target, time.time())

        self.sock.sendto(data, target)

    def cleanup_expired_mappings(self) -> None:
        """
        Session removal works in multiple steps:
        1. Check if role is active: a role is considered active if any of its
           ports has been active within the timeout period
        2. Remove role from sesssion if it has not been active: Clear the role
           in the session, remove from sessions address list and remove from
           mappings
        3. If all of a sessions roles have been cleared, remove the session
           completely
        """
        now = time.time()

        with self.lock:
            expired_roles: Dict[str, List[Role]] = {}

            # Identify expired roles
            for sid, session in self.sessions.items():
                # Ignore sessions with active announcements
                if (now - session.last_announcement_at) > self.timeout:
                    for r, role in session.roles.items():
                        if not role:
                            continue

                        with self.mapping_lock:
                            role_expired = True
                            for _, peer in role.items():
                                mapping = self.mappings.get(peer.addr)
                                if mapping:
                                    _, ts = mapping
                                    if (now - ts) < self.timeout:
                                        role_expired = False
                                        break

                            if role_expired:
                                if sid not in expired_roles:
                                    expired_roles[sid] = []

                                expired_roles[sid].append(r)

            # Remove expired roles
            for sid, roles_to_remove in expired_roles.items():
                session = self.sessions[sid]
                for r in roles_to_remove:
                    role = session.roles[r]
                    with self.mapping_lock:
                        for _, peer in role.items():
                            session.addresses.remove(peer.addr)
                            self.mappings.pop(peer.addr, None)

                    session.roles[r] = {}
                    logging.info(f"{sid}: Removed expired mappings for {r.name}")

            # Remove session with no active roles
            expired_sessions: List[str] = []
            for sid, session in self.sessions.items():
                if len(session.addresses) == 0:
                    expired_sessions.append(sid)

            for sid in expired_sessions:
                del self.sessions[sid]
                logging.info(f"{sid}: Removed expired session")

            """
            orphaned_sessions: Set[str] = set()
            for sid in self.sessions:
                session = self.sessions[sid]
                if (
                    (now - session.last_announcement_at) > self.timeout and
                    not session.is_ready()
                ):
                    orphaned_sessions.add(sid)

            for sid in orphaned_sessions:
                del self.sessions[sid]
                logging.info(f"{sid}: Removed orphaned session")

            expired_mappings: List[Address] = []
            with self.mapping_lock:
                for addr, (_, ts) in self.mappings.items():
                    if (now - ts) > self.timeout:
                        expired_mappings.append(addr)

                affected_sessions: Set[str] = set()
                for addr in expired_mappings:
                    sids = self._get_sids_for_address_unlocked(addr)
                    for sid in sids:
                        affected_sessions.add(sid)

                        del self.mappings[addr]
                        logging.info(f"{sid}: Removed expired mapping for {addr}")

                    if len(affected_sessions) == 0:
                        del self.mappings[addr]
                        logging.info(f"Removed unassociated, expired mapping for {addr}")

                expired_sessions: Set[str] = set()
                for sid in affected_sessions:
                    session = self.sessions.get(sid)
                    if session:
                        has_active_mappings = False
                        for addr in session.addresses:
                            if addr in self.mappings:
                                has_active_mappings = True
                                break

                        if not has_active_mappings:
                            expired_sessions.add(sid)

            for sid in expired_sessions:
                del self.sessions[sid]
                logging.info(f"{sid}: Removed expired session")
            """

    def _send_peer_info(self, session: Session) -> None:
        peers = session.roles
        try:
            peer_info = PeerInfo(ip=self.ip, video_port=self.port, control_port=self.port)
            for role_peers in peers.values():
                for peer in role_peers.values():
                    self.sock.sendto(peer_info.to_bytes(), peer.addr)

        except Exception as e:
            logging.error(f"Error sending PeerInfo: {e}", exc_info=True)

    def _get_sids_for_address_unlocked(self, addr: Address) -> Set[str]:
        """Caller is required to hold the lock."""
        sids: Set[str] = set()
        for sid in self.sessions:
            session = self.sessions[sid]
            if addr in session.addresses:
                sids.add(sid)

        return sids

    def _update_mappings(self, session: Session) -> None:
        """Update relay mappings for a ready session. Must be called with lock held."""
        streamer_peers = session.roles.get(Role.STREAMER, {})
        viewer_peers = session.roles.get(Role.VIEWER, {})

        if (
            len(streamer_peers) != len(PortType) or
            len(viewer_peers) != len(PortType)
        ):
            return

        now = time.time()
        new_mappings: Dict[Address, tuple[Address, float]] = {}
        session_addresses: Set[Address] = set()

        for port_type in PortType:
            if (
                port_type in streamer_peers and
                port_type in viewer_peers
            ):
                streamer_addr = streamer_peers[port_type].addr
                viewer_addr = viewer_peers[port_type].addr

                new_mappings[streamer_addr] = (viewer_addr, now)
                new_mappings[viewer_addr] = (streamer_addr, now)

                session_addresses.add(streamer_addr)
                session_addresses.add(viewer_addr)

        overwritten: Set[str] = set()
        with self.mapping_lock:
            # Remove mapping that might have existed for this sessions addresses
            # before
            for addr in session.addresses:
                # If addr already exists in mappings, it could also be for a
                # session which ID has been renewed, we need to delete the
                # session if any exists.
                sids = self._get_sids_for_address_unlocked(addr)
                overwritten = overwritten.union(sids)
                self.mappings.pop(addr, None)

            # Update with new mappings
            self.mappings.update(new_mappings)

        for sid in overwritten:
            if sid != session.id:
                del self.sessions[sid]
                logging.info(f"{sid}: Removed overwritten session")
