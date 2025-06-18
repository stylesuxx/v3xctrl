"""
Simple UDP relay

Sessions are matched based on their ID, each session needs a server and a
client.

Session mapping is kept alive as long as a peer keeps re-announcing or active
communication is happening over either of the ports.

Relay mappings are removed after a certain time of inactivity and allow to be
re-established if the peer shows up again.
"""
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import logging
import socket
import threading
import time

from v3xctrl_control.Message import Message, PeerAnnouncement, PeerInfo, Error
from v3xctrl_udp_relay.SessionStore import SessionStore


Addr = tuple[str, int]


class Role(Enum):
    STREAMER = "streamer"
    VIEWER = "viewer"


class PortType(Enum):
    VIDEO = "video"
    CONTROL = "control"


class PeerEntry:
    def __init__(self, addr):
        self.addr = addr
        self.ts = time.time()


class Session:
    def __init__(self):
        self.roles = {
            Role.STREAMER: {},
            Role.VIEWER: {}
        }

    def register(self, role: Role, port_type: PortType, addr):
        new_peer = port_type not in self.roles[role]
        self.roles[role][port_type] = PeerEntry(addr)

        return new_peer

    def is_ready(self, role: Role):
        for port_type in PortType:
            if port_type not in self.roles[role]:
                return False

        return True

    def get_peer(self, role: Role, port_type):
        return self.roles[role].get(port_type)


class UDPRelayServer(threading.Thread):
    TIMEOUT = 3600
    CLEANUP_INTERVAL = 1
    RECEIVE_BUFFER = 2048

    def __init__(self, ip: str, port: int, db_path: str):
        super().__init__(daemon=True, name="UDPRelayServer")
        self.ip = ip
        self.port = port
        self.store = SessionStore(db_path)

        self.sessions: dict[str, Session] = {}
        self.relay_map: dict[Addr, dict] = {}

        self.lock = threading.Lock()
        self.relay_lock = threading.Lock()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', self.port))

        self.executor = ThreadPoolExecutor(max_workers=10)

        self.running = threading.Event()
        self.running.set()

    def _is_mapping_expired(self, mapping: dict, now: float) -> bool:
        return (now - mapping["ts"]) > self.TIMEOUT

    def _clean_expired_entries(self) -> None:
        while self.running.is_set():
            now = time.time()
            expired_roles = {}

            with self.relay_lock:
                # Phase 1: Identify expired mappings per (session, role)
                for addr, entry in list(self.relay_map.items()):
                    if self._is_mapping_expired(entry, now):
                        key = (entry["session"], entry["role"])
                        expired_roles.setdefault(key, set()).add(entry["port_type"])

                # Phase 2: Expire relay mappings and roles
                for (session_id, role), expired_types in expired_roles.items():
                    if all(pt in expired_types for pt in PortType):
                        for addr, entry in list(self.relay_map.items()):
                            if entry["session"] == session_id and entry["role"] == role:
                                del self.relay_map[addr]
                                logging.info(f"Expired mapping for {session_id}:{role}:{entry['port_type']} at {addr}")

                        if session_id in self.sessions:
                            self.sessions[session_id].roles[role] = {}
                            logging.info(f"Removed expired role {role} from session {session_id}")

                # Phase 3: Expire whole session if:
                # - it has no relay mappings AND
                # - no recent PeerEntry timestamps
                for sid, session in list(self.sessions.items()):
                    has_mapping = any(
                        entry["session"] == sid for entry in self.relay_map.values()
                    )

                    if has_mapping:
                        continue

                    all_expired = True
                    for role_dict in session.roles.values():
                        for peer in role_dict.values():
                            if (now - peer.ts) <= self.TIMEOUT:
                                all_expired = False
                                break
                        if not all_expired:
                            break

                    if all_expired:
                        del self.sessions[sid]
                        logging.info(f"Removed expired session: {sid}")

            time.sleep(self.CLEANUP_INTERVAL)

    def _handle_peer_announcement(self, msg: PeerAnnouncement, addr: Addr):
        """Registers peers and sets up relay mappings if both sides are ready."""
        session_id = msg.get_id()

        role = None
        port_type = None

        try:
            role = Role(msg.get_role())
            port_type = PortType(msg.get_port_type())
        except ValueError:
            logging.debug(f"Invalid announcement from {addr} — role={msg.get_role()}, port_type={msg.get_port_type()}")
            return

        other_role = Role.VIEWER if role == Role.STREAMER else Role.STREAMER
        now = time.time()
        with self.lock:
            if not self.store.exists(session_id):
                logging.info(f"Ignoring announcement for unknown session '{session_id}' from {addr}")

                try:
                    error_msg = Error(403)
                    self.sock.sendto(error_msg.to_bytes(), addr)
                except Exception as e:
                    logging.error(f"Failed to send error message to {addr}: {e}", exc_info=True)

                return

            session = self.sessions.setdefault(session_id, Session())
            is_new_peer = session.register(role, port_type, addr)
            if is_new_peer:
                logging.info(f"Registered {role.name}:{port_type.name} for session '{session_id}' from {addr}")

            if session.is_ready(role) and session.is_ready(other_role):
                for port_type in PortType:
                    client = session.get_peer(Role.STREAMER, port_type)
                    server = session.get_peer(Role.VIEWER, port_type)

                    if not client or not server:
                        continue

                    with self.relay_lock:
                        # Remove stale entries for this session + port_type
                        for addr, entry in list(self.relay_map.items()):
                            if (entry["session"] == session_id and entry["port_type"] == port_type):
                                del self.relay_map[addr]

                        # Insert updated mapping
                        self.relay_map[client.addr] = {
                            "target": server.addr,
                            "ts": now,
                            "session": session_id,
                            "role": Role.STREAMER,
                            "port_type": port_type
                        }
                        self.relay_map[server.addr] = {
                            "target": client.addr,
                            "ts": now,
                            "session": session_id,
                            "role": Role.VIEWER,
                            "port_type": port_type
                        }

                try:
                    peer_info = PeerInfo(ip=self.ip, video_port=self.port, control_port=self.port)
                    for port_type in PortType:
                        for role in Role:
                            self.sock.sendto(
                                peer_info.to_bytes(),
                                session.get_peer(role, port_type).addr
                            )

                    logging.info(f"Peer info exchanged: '{session_id}'")

                except Exception as e:
                    logging.error(f"Error sending PeerInfo: {e}", exc_info=True)

    def _forward_packet(self, data: bytes, addr: Addr):
        with self.relay_lock:
            entry = self.relay_map.get(addr)
            if entry:
                self.sock.sendto(data, entry["target"])
                entry["ts"] = time.time()

    def _handle_packet(self, data: bytes, addr: Addr) -> None:
        try:
            if data.startswith(b'\x83\xa1t\xb0PeerAnnouncement'):
                try:
                    msg = Message.from_bytes(data)
                    if isinstance(msg, PeerAnnouncement):
                        self._handle_peer_announcement(msg, addr)
                        return
                except Exception:
                    logging.debug("Malformed peer announcement")
                    return

            if addr in self.relay_map:
                self._forward_packet(data, addr)
        except Exception as e:
            logging.error(f"Error handling packet from {addr}: {e}", exc_info=True)

    def run(self) -> None:
        logging.info(f"UDP Relay server listening on {self.ip}:{self.port}")
        threading.Thread(target=self._clean_expired_entries, daemon=True).start()

        while self.running.is_set():
            try:
                data, addr = self.sock.recvfrom(self.RECEIVE_BUFFER)
                self.executor.submit(self._handle_packet, data, addr)

            except OSError:
                if not self.running.is_set():
                    break
                logging.error("Socket error")
            except Exception as e:
                logging.error(f"Unhandled error: {e}", exc_info=True)

    def shutdown(self) -> None:
        """Stops the relay server and closes the socket."""
        self.running.clear()
        try:
            self.sock.close()
        except Exception as e:
            logging.warning(f"Error closing socket: {e}")
