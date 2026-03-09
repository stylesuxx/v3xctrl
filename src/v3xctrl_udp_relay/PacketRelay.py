import logging
import socket
import threading
import time

logger = logging.getLogger(__name__)

from v3xctrl_helper import Address
from v3xctrl_control.message import (
    Error,
    PeerInfo,
    PeerAnnouncement
)
from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.Role import Role
from v3xctrl_udp_relay.ForwardTarget import ForwardTarget, UdpTarget, TcpTarget
from v3xctrl_tcp import Transport
from v3xctrl_udp_relay.custom_types import (
    PortType,
    Session,
    PeerEntry,
    SpectatorEntry,
)


class Mapping:
    __slots__ = ('targets', 'timestamp')

    def __init__(self, targets: set[Address], timestamp: float) -> None:
        self.targets = targets
        self.timestamp = timestamp


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

    Lock ordering:
        session_lock -> mapping_lock (always acquire in this order, never reverse)
        - session_lock protects session state (sessions, spectator_by_address)
        - mapping_lock protects hot-path forwarding (mappings, tcp_targets)
        - NEVER acquire session_lock while holding mapping_lock
    """

    SPECTATOR_TIMEOUT = 30

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

        self.mappings: dict[Address, Mapping] = {}
        self.sessions: dict[str, Session] = {}

        # Address -> TcpTarget for peers that registered via TCP
        self.tcp_targets: dict[Address, TcpTarget] = {}

        # Reverse index: spectator address -> SpectatorEntry for O(1) heartbeat lookup
        self.spectator_by_address: dict[Address, SpectatorEntry] = {}

        # Protects session state: self.sessions, self.spectator_by_address
        self.session_lock = threading.Lock()

        # Protects hot-path forwarding: self.mappings, self.tcp_targets
        self.mapping_lock = threading.Lock()

    def register_tcp_peer(self, msg: PeerAnnouncement, addr: Address, target: TcpTarget) -> None:
        with self.mapping_lock:
            self.tcp_targets[addr] = target
        self.register_peer(msg, addr)

    def _get_target(self, addr: Address) -> ForwardTarget:
        tcp_target = self.tcp_targets.get(addr)
        if tcp_target and tcp_target.is_alive():
            return tcp_target

        return UdpTarget(self.sock, addr)

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
            logger.warning(f"Invalid announcement from {addr}: role='{msg.get_role()}', port_type='{msg.get_port_type()}'")
            return

        sid = msg.get_id()

        with self.session_lock:
            match role:
                case Role.STREAMER | Role.VIEWER:
                    self._remove_spectator_from_all_sessions(addr)
                    if not self.store.exists(sid):
                        logger.info(f"Ignoring announcement for unknown session '{sid}' from {addr}")
                        try:
                            error_msg = Error(str(403))
                            self._get_target(addr).send(error_msg.to_bytes())
                        except Exception as e:
                            logger.error(f"Failed to send error message to {addr}: {e}", exc_info=True)

                        return

                case Role.SPECTATOR:
                    actual_sid = self.store.get_session_id_from_spectator_id(sid)
                    if not actual_sid:
                        logger.info(f"Ignoring spectator announcement for unknown spectator ID '{sid}' from {addr}")
                        try:
                            error_msg = Error(str(403))
                            self._get_target(addr).send(error_msg.to_bytes())
                        except Exception as e:
                            logger.error(f"Failed to send error message to {addr}: {e}", exc_info=True)
                        return
                    sid = actual_sid
                    logger.info(f"Spectator using spectator_id, mapped to session '{sid}'")

            session = self.sessions.setdefault(sid, Session(sid))
            new_transport = Transport.TCP if addr in self.tcp_targets else Transport.UDP

            if role != Role.SPECTATOR:
                old_entry = session.roles.get(role, {}).get(port_type)
                old_transport = old_entry.transport if old_entry else None

            is_new_peer, replaced_addr = session.register(role, port_type, addr, new_transport)

            if role == Role.SPECTATOR:
                if replaced_addr:
                    self.spectator_by_address.pop(replaced_addr, None)
                    with self.mapping_lock:
                        self._remove_spectator_addr_from_mappings(replaced_addr, session)

                for spectator in session.spectators:
                    if addr in spectator.get_addresses():
                        self.spectator_by_address[addr] = spectator
                        break

                if session.is_ready():
                    self._setup_spectator_mappings(session, addr)
                    self._send_peer_info_to_spectator(session, addr)
                    logger.info(f"{sid}: Spectator {addr} joined ready session")
                else:
                    logger.info(f"{sid}: Spectator {addr} waiting for session to be ready")

                # Spectators will not make a session ready, return early
                return

            if is_new_peer:
                logger.info(f"{sid}: Registered {role.name}:{port_type.name} ({new_transport.name}) from {addr}")
            elif old_transport and old_transport != new_transport:
                logger.info(f"{sid}: {role.name}:{port_type.name} switched {old_transport.name} -> {new_transport.name}")

            if session.is_ready():
                self._update_mappings(session)
                self._send_peer_info(session)
                self._setup_all_spectator_mappings(session)
                self._send_peer_info_to_all_spectators(session)

                transports = self._get_transport_summary(session)
                logger.info(f"{sid}: Session ready, peer info exchanged ({transports})")

    def get_session_peers(self, sid: str) -> dict[Role, dict[PortType, PeerEntry]]:
        """Get all peers for a session."""
        with self.session_lock:
            session = self.sessions.get(sid)
            if not session:
                return {}

            return session.roles

    def update_spectator_heartbeat(self, addr: Address) -> None:
        with self.session_lock:
            spectator = self.spectator_by_address.get(addr)
            if spectator:
                spectator.last_announcement_at = time.time()

    def _remove_spectator_from_all_sessions(self, addr: Address) -> None:
        for sid, session in self.sessions.items():
            spectator_addresses = session.remove_spectator_by_address(addr)
            if spectator_addresses:
                for spectator_addr in spectator_addresses:
                    self.spectator_by_address.pop(spectator_addr, None)

                with self.mapping_lock:
                    self._remove_spectator_from_mappings(spectator_addresses, session)

                logger.info(f"{sid}: Removed spectator at {addr}")
                return

    def forward_packet(
        self,
        data: bytes,
        addr: Address
    ) -> list[TcpTarget] | None:
        """
        Forward a packet to its mapped targets.

        Returns None if no mapping exists. Otherwise returns a list of
        TcpTarget instances whose sends were deferred (caller must submit
        them to the thread pool). UDP sends happen inline.
        """
        with self.mapping_lock:
            mapping = self.mappings.get(addr)
            if not mapping:
                return None

            mapping.timestamp = time.time()

        deferred_tcp: list[TcpTarget] = []
        for target in mapping.targets:
            tcp_target = self.tcp_targets.get(target)
            if not tcp_target:
                self.sock.sendto(data, target)
            elif tcp_target.is_alive():
                deferred_tcp.append(tcp_target)

        return deferred_tcp

    def cleanup_expired_mappings(self) -> None:
        """
        Session removal works in multiple steps:
        1. Remove dead TCP targets that have no active mapping
        2. Identify and remove roles whose mappings have expired
        3. Remove inactive spectators from sessions that still have active roles
        4. Remove sessions where all roles are empty
        """
        self._cleanup_dead_tcp_targets()
        with self.session_lock:
            now = time.time()
            self._cleanup_expired_roles(now)
            self._cleanup_inactive_spectators(now)
            self._cleanup_empty_sessions()

    def _cleanup_dead_tcp_targets(self) -> None:
        """Remove TCP targets that are dead and have no active mapping."""
        with self.mapping_lock:
            dead = [
                addr for addr, target in self.tcp_targets.items()
                if not target.is_alive() and addr not in self.mappings
            ]
            for addr in dead:
                del self.tcp_targets[addr]

    def _cleanup_expired_roles(self, now: float) -> None:
        """Identify and remove roles whose mappings have all expired. Caller must hold session_lock."""
        expired_roles_by_session: dict[str, list[Role]] = {}

        for sid, session in self.sessions.items():
            if (now - session.last_announcement_at) <= self.timeout:
                continue

            for role, peers_by_port in session.roles.items():
                if len(peers_by_port) == 0:
                    continue

                with self.mapping_lock:
                    all_expired = all(
                        (mapping := self.mappings.get(peer.addr)) is None
                        or (now - mapping.timestamp) >= self.timeout
                        for peer in peers_by_port.values()
                    )

                    if all_expired:
                        expired_roles_by_session.setdefault(sid, []).append(role)

        for sid, roles_to_remove in expired_roles_by_session.items():
            session = self.sessions[sid]
            for role in roles_to_remove:
                peers_by_port = session.roles[role]
                with self.mapping_lock:
                    for peer in peers_by_port.values():
                        session.addresses.discard(peer.addr)
                        self.mappings.pop(peer.addr, None)

                session.roles[role] = {}
                logger.info(f"{sid}: Removed expired mappings for {role.name}")

    def _cleanup_inactive_spectators(self, now: float) -> None:
        """Remove spectators that stopped sending heartbeats and have no active TCP. Caller must hold session_lock."""
        expired_session_ids = {
            sid for sid, session in self.sessions.items()
            if all(len(peers_by_port) == 0 for peers_by_port in session.roles.values())
        }

        for sid, session in self.sessions.items():
            if sid in expired_session_ids:
                continue

            for i in reversed(range(len(session.spectators))):
                spectator = session.spectators[i]
                if (now - spectator.last_announcement_at) > self.SPECTATOR_TIMEOUT:
                    if self._spectator_has_active_tcp(spectator):
                        spectator.last_announcement_at = now
                        continue

                    with self.mapping_lock:
                        spectator_addrs = spectator.get_addresses()
                        for addr in spectator_addrs:
                            session.addresses.discard(addr)
                            self.spectator_by_address.pop(addr, None)
                        self._remove_spectator_from_mappings(spectator_addrs, session)

                    del session.spectators[i]
                    logger.info(f"{sid}: Removed inactive spectator")

    def _cleanup_empty_sessions(self) -> None:
        """Remove sessions where all roles are empty, cleaning up their spectators. Caller must hold session_lock."""
        expired_session_ids = [
            sid for sid, session in self.sessions.items()
            if all(len(peers_by_port) == 0 for peers_by_port in session.roles.values())
        ]

        for sid in expired_session_ids:
            session = self.sessions[sid]
            for spectator in session.spectators:
                for addr in spectator.get_addresses():
                    self.spectator_by_address.pop(addr, None)
                with self.mapping_lock:
                    self._remove_spectator_from_mappings(spectator.get_addresses(), session)

            del self.sessions[sid]
            logger.info(f"{sid}: Removed expired session")

    def _send_peer_info(self, session: Session) -> None:
        peers = session.roles
        try:
            peer_info = PeerInfo(ip=self.ip, video_port=self.port, control_port=self.port)
            for role_peers in peers.values():
                for peer in role_peers.values():
                    self._get_target(peer.addr).send(peer_info.to_bytes())

        except Exception as e:
            logger.error(f"Error sending PeerInfo: {e}", exc_info=True)

    def _send_peer_info_to_spectator(self, session: Session, spectator_addr: Address) -> None:
        """Send peer info to a specific spectator address."""
        try:
            peer_info = PeerInfo(ip=self.ip, video_port=self.port, control_port=self.port)
            self._get_target(spectator_addr).send(peer_info.to_bytes())

        except Exception as e:
            logger.error(f"Error sending PeerInfo to spectator {spectator_addr}: {e}", exc_info=True)

    def _send_peer_info_to_all_spectators(self, session: Session) -> None:
        """Send peer info to all spectators in the session."""
        for spectator in session.spectators:
            for peer_entry in spectator.ports.values():
                self._send_peer_info_to_spectator(session, peer_entry.addr)

    def _get_sids_for_address_unlocked(self, addr: Address) -> set[str]:
        """Caller is required to hold the lock."""
        sids: set[str] = set()
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
        new_mappings: dict[Address, Mapping] = {}
        session_addresses: set[Address] = set()

        for port_type in PortType:
            if (
                port_type in streamer_peers and
                port_type in viewer_peers
            ):
                streamer_addr = streamer_peers[port_type].addr
                viewer_addr = viewer_peers[port_type].addr

                new_mappings[streamer_addr] = Mapping({viewer_addr}, now)
                new_mappings[viewer_addr] = Mapping({streamer_addr}, now)

                session_addresses.add(streamer_addr)
                session_addresses.add(viewer_addr)

        overwritten: set[str] = set()
        with self.mapping_lock:
            # Preserve timestamps for unchanged mappings so re-announcements
            # don't reset the timeout for inactive peers.
            for addr, new_mapping in new_mappings.items():
                existing = self.mappings.get(addr)
                if existing and existing.targets == new_mapping.targets:
                    new_mapping.timestamp = existing.timestamp

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
                logger.info(f"{sid}: Removed overwritten session")

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

                    existing_mapping = self.mappings.get(streamer_addr)
                    if existing_mapping:
                        existing_mapping.targets = existing_mapping.targets | {spectator_port_addr}
                        existing_mapping.timestamp = now
                    else:
                        self.mappings[streamer_addr] = Mapping({spectator_port_addr}, now)

    def _setup_all_spectator_mappings(self, session: Session) -> None:
        """Setup mappings for all spectators in a session."""
        for spectator in session.spectators:
            if spectator.is_complete():
                for port_addr in spectator.get_addresses():
                    self._setup_spectator_mappings(session, port_addr)

    def _get_transport_summary(self, session: Session) -> str:
        """Build a transport summary string like 'STREAMER: TCP, VIEWER: UDP'."""
        parts = []
        for role in (Role.STREAMER, Role.VIEWER):
            peers = session.roles.get(role, {})
            transports = {p.transport for p in peers.values()}
            if len(transports) == 1:
                parts.append(f"{role.name}: {transports.pop().name}")
            elif transports:
                detail = ", ".join(f"{pt.name}={p.transport.name}" for pt, p in peers.items())
                parts.append(f"{role.name}: {detail}")
        return ", ".join(parts)

    def _spectator_has_active_tcp(self, spectator: SpectatorEntry) -> bool:
        """Check if a spectator has any active TCP connection. Acquires mapping_lock."""
        with self.mapping_lock:
            for addr in spectator.get_addresses():
                target = self.tcp_targets.get(addr)
                if target and target.is_alive():
                    return True

        return False

    def _remove_spectator_addr_from_mappings(self, spectator_addr: Address, session: Session) -> None:
        """Remove a single spectator address from streamer mapping targets. Caller must hold mapping_lock."""
        self._remove_spectator_from_mappings({spectator_addr}, session)

    def _remove_spectator_from_mappings(self, spectator_addrs: set[Address], session: Session) -> None:
        """Remove spectator addresses from streamer mapping targets. Caller must hold mapping_lock."""
        streamer_peers = session.roles.get(Role.STREAMER, {})
        for spectator_addr in spectator_addrs:
            for peer in streamer_peers.values():
                streamer_addr = peer.addr
                mapping = self.mappings.get(streamer_addr)
                if mapping and spectator_addr in mapping.targets:
                    mapping.targets = mapping.targets - {spectator_addr}
