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

        # General lock, when execution is not hot path
        self.lock = threading.Lock()

        # Only lock mappings when absolutely necessary
        self.mapping_lock = threading.Lock()

    def register_tcp_peer(self, msg: PeerAnnouncement, addr: Address, target: TcpTarget) -> None:
        with self.mapping_lock:
            self.tcp_targets[addr] = target
        self.register_peer(msg, addr)

    def unregister_tcp_peer(self, addr: Address) -> None:
        with self.mapping_lock:
            self.tcp_targets.pop(addr, None)

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

        with self.lock:
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

            is_new_peer = session.register(role, port_type, addr, new_transport)

            if role == Role.SPECTATOR:
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

                transports = self._get_transport_summary(session)
                logger.info(f"{sid}: Session ready, peer info exchanged ({transports})")

    def get_session_peers(self, sid: str) -> dict[Role, dict[PortType, PeerEntry]]:
        """Get all peers for a session."""
        with self.lock:
            session = self.sessions.get(sid)
            if not session:
                return {}

            return session.roles

    def update_spectator_heartbeat(self, addr: Address) -> None:
        with self.lock:
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

            now = time.time()
            mapping.timestamp = now

            for target_addr in mapping.targets:
                target_mapping = self.mappings.get(target_addr)
                if target_mapping:
                    target_mapping.timestamp = now

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
        1. Check if role is active: a role is considered active if any of its
           ports has been active within the timeout period
        2. Remove role from sesssion if it has not been active: Clear the role
           in the session, remove from sessions address list and remove from
           mappings
        3. If all of a sessions roles have been cleared, remove the session
           completely
        """
        now = time.time()

        with self.mapping_lock:
            dead = [a for a, t in self.tcp_targets.items() if not t.is_alive()]
            for a in dead:
                del self.tcp_targets[a]

        with self.lock:
            expired_roles: dict[str, list[Role]] = {}

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
                                        if (now - mapping.timestamp) < self.timeout:
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
                    logger.info(f"{sid}: Removed expired mappings for {r.name}")

            # Identify sessions with no active roles (spectators don't count)
            expired_sessions: list[str] = []
            for sid, session in self.sessions.items():
                expired = True
                for _, role in session.roles.items():
                    if len(role) > 0:
                        expired = False

                if expired:
                    expired_sessions.append(sid)

            # Clean up inactive spectators from active sessions
            # Spectators must send announcements or maintain a TCP connection to stay active
            for sid, session in self.sessions.items():
                if sid not in expired_sessions:
                    for i in reversed(range(len(session.spectators))):
                        spectator = session.spectators[i]
                        if (now - spectator.last_announcement_at) > self.SPECTATOR_TIMEOUT:
                            has_active_tcp = False
                            with self.mapping_lock:
                                for addr in spectator.get_addresses():
                                    target = self.tcp_targets.get(addr)
                                    if target and target.is_alive():
                                        has_active_tcp = True
                                        break

                            if has_active_tcp:
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

            # Remove expired sessions and cleanup their spectators
            for sid in expired_sessions:
                session = self.sessions[sid]
                # Clean up spectator mappings before deleting session
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

    def _remove_spectator_from_mappings(self, spectator_addrs: set[Address], session: Session) -> None:
        """Remove spectator addresses from streamer mapping targets. Caller must hold mapping_lock."""
        streamer_peers = session.roles.get(Role.STREAMER, {})
        for spectator_addr in spectator_addrs:
            for peer in streamer_peers.values():
                streamer_addr = peer.addr
                mapping = self.mappings.get(streamer_addr)
                if mapping and spectator_addr in mapping.targets:
                    mapping.targets = mapping.targets - {spectator_addr}
