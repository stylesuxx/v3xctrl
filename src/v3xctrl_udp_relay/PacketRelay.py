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
from v3xctrl_udp_relay.Role import Role
from v3xctrl_udp_relay.custom_types import (
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

            if role == Role.SPECTATOR:
                if session.is_ready():
                    self._setup_spectator_mappings(session, addr)
                    self._send_peer_info_to_spectator(session, addr)
                    logging.info(f"{sid}: Spectator {addr} joined ready session")
                else:
                    logging.info(f"{sid}: Spectator {addr} waiting for session to be ready")

                # Spectators will not make a session ready, return early
                return

            if session.is_ready():
                self._update_mappings(session)
                self._send_peer_info(session)
                self._setup_all_spectator_mappings(session)

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

            targets, _ = mapping
            self.mappings[addr] = (targets, time.time())

        # Send to all targets (viewer + spectators for streamer, or just streamer for viewer)
        for target in targets:
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
                        # Ignore empty roles
                        if len(role) > 0:
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
                            session.addresses.discard(peer.addr)
                            self.mappings.pop(peer.addr, None)

                    session.roles[r] = {}
                    logging.info(f"{sid}: Removed expired mappings for {r.name}")

            # Identify sessions with no active roles (spectators don't count)
            expired_sessions: List[str] = []
            for sid, session in self.sessions.items():
                expired = True
                for _, role in session.roles.items():
                    if len(role) > 0:
                        expired = False

                if expired:
                    expired_sessions.append(sid)

            # Clean up spectators from expired sessions
            # Spectators don't send data, so we can't check their activity.
            # They are removed when their session expires (no active streamer/viewer).
            for sid in expired_sessions:
                session = self.sessions[sid]
                for idx in reversed(range(len(session.spectators))):
                    spectator = session.spectators[idx]
                    streamer_peers = session.roles.get(Role.STREAMER, {})

                    with self.mapping_lock:
                        for port_addr in spectator.get_addresses():
                            session.addresses.discard(port_addr)
                            # Remove spectator from streamer's target set (if any)
                            for port_type, peer in streamer_peers.items():
                                streamer_addr = peer.addr
                                if streamer_addr in self.mappings:
                                    targets, ts = self.mappings[streamer_addr]
                                    if isinstance(targets, set) and port_addr in targets:
                                        targets.discard(port_addr)
                                        self.mappings[streamer_addr] = (targets, ts)

                    del session.spectators[idx]
                    logging.info(f"{sid}: Removed spectator at index {idx} (session expiring)")

            # Remove expired sessions
            for sid in expired_sessions:
                del self.sessions[sid]
                logging.info(f"{sid}: Removed expired session")

    def _send_peer_info(self, session: Session) -> None:
        peers = session.roles
        try:
            peer_info = PeerInfo(ip=self.ip, video_port=self.port, control_port=self.port)
            for role_peers in peers.values():
                for peer in role_peers.values():
                    self.sock.sendto(peer_info.to_bytes(), peer.addr)

        except Exception as e:
            logging.error(f"Error sending PeerInfo: {e}", exc_info=True)

    def _send_peer_info_to_spectator(self, session: Session, spectator_addr: Address) -> None:
        """Send peer info to a specific spectator address."""
        try:
            peer_info = PeerInfo(ip=self.ip, video_port=self.port, control_port=self.port)
            self.sock.sendto(peer_info.to_bytes(), spectator_addr)
        except Exception as e:
            logging.error(f"Error sending PeerInfo to spectator {spectator_addr}: {e}", exc_info=True)

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
        new_mappings: Dict[Address, tuple[Set[Address], float]] = {}
        session_addresses: Set[Address] = set()

        for port_type in PortType:
            if (
                port_type in streamer_peers and
                port_type in viewer_peers
            ):
                streamer_addr = streamer_peers[port_type].addr
                viewer_addr = viewer_peers[port_type].addr

                new_mappings[streamer_addr] = ({viewer_addr}, now)
                new_mappings[viewer_addr] = ({streamer_addr}, now)

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

    def _setup_spectator_mappings(self, session: Session, spectator_addr: Address) -> None:
        """
        Setup mappings for a spectator to receive streamer data.
        Spectators only receive from streamer, they don't send anything back.
        """
        # Find the spectator entry by address
        spectator_entry = None
        for spectator in session.spectators:
            if spectator_addr in spectator.get_addresses():
                spectator_entry = spectator
                break

        if not spectator_entry or not spectator_entry.is_complete():
            return

        streamer_peers = session.roles.get(Role.STREAMER, {})
        if len(streamer_peers) != len(PortType):
            return

        now = time.time()
        with self.mapping_lock:
            # Map streamer addresses to spectator addresses (one-way)
            for port_type in PortType:
                if port_type in streamer_peers and port_type in spectator_entry.ports:
                    streamer_addr = streamer_peers[port_type].addr
                    spectator_port_addr = spectator_entry.ports[port_type].addr

                    # Get existing mapping for streamer (viewer might already be mapped)
                    existing_targets = self._get_spectator_targets(streamer_addr)
                    existing_targets.add(spectator_port_addr)
                    self.mappings[streamer_addr] = (existing_targets, now)

    def _setup_all_spectator_mappings(self, session: Session) -> None:
        """Setup mappings for all spectators in a session."""
        for spectator in session.spectators:
            if spectator.is_complete():
                for port_addr in spectator.get_addresses():
                    self._setup_spectator_mappings(session, port_addr)

    def _get_spectator_targets(self, source_addr: Address) -> Set[Address]:
        """Get existing spectator targets for a source address."""
        if source_addr in self.mappings:
            targets, _ = self.mappings[source_addr]
            return targets.copy()
        return set()

