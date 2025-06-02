"""
Simple UDP relay

Sessions are matched based on their ID, each session needs a server and a
client.

Session mapping is kept alive as long as a peer keeps re-announcing or active
communication is happening over either of the ports.

Relay mappings are removed after a certain time of inactivity and allow to be
re-established if the peer shows up again.
"""

from enum import Enum
import logging
import socket
import threading
import time

from v3xctrl_control.Message import Message, PeerAnnouncement, PeerInfo


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
    TIMEOUT = 10
    CLEANUP_INTERVAL = 1
    RECEIVE_BUFFER = 2048

    def __init__(self, ip: str, port: int):
        super().__init__(daemon=True)
        self.ip = ip
        self.port = port

        self.sessions = {}
        self.relay_map = {}

        self.lock = threading.Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', self.port))

        self.running = threading.Event()
        self.running.set()

    def _is_entry_expired(self, entry, now):
        return (now - entry["ts"]) > self.TIMEOUT

    def clean_expired_entries(self):
        while self.running.is_set():
            now = time.time()
            expired_roles = {}

            with self.lock:
                # Phase 1: Identify expired mappings per (session, role)
                for addr, entry in list(self.relay_map.items()):
                    if self._is_entry_expired(entry, now):
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

    def handle_peer_announcement(self, msg: PeerAnnouncement, addr):
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
            session = self.sessions.setdefault(session_id, Session())
            is_new_peer = session.register(role, port_type, addr)
            if is_new_peer:
                logging.info(f"Registered {role.name}:{port_type.name} for session '{session_id}' from {addr}")

            if session.is_ready(role) and session.is_ready(other_role):
                is_first_time = True
                for port_type in PortType:
                    client = session.get_peer(Role.STREAMER, port_type)
                    server = session.get_peer(Role.VIEWER, port_type)

                    if not client or not server:
                        continue

                    if client.addr in self.relay_map or server.addr in self.relay_map:
                        is_first_time = False

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

                    if is_first_time:
                        for port_type in PortType:
                            for role in Role:
                                self.sock.sendto(
                                    peer_info.to_bytes(),
                                    session.get_peer(role, port_type).addr
                                )

                        logging.info(f"New session established: '{session_id}'")

                    else:
                        for port_type, peer in session.roles[role].items():
                            self.sock.sendto(peer_info.to_bytes(), peer.addr)

                        logging.info(f"Existing session reconnected: '{session_id}'")

                except Exception as e:
                    logging.error(f"Error sending PeerInfo: {e}", exc_info=True)

    def forward_packet(self, data, addr):
        entry = self.relay_map.get(addr)
        if entry:
            self.sock.sendto(data, entry["target"])
            entry["ts"] = time.time()

    def run(self):
        logging.info(f"UDP Relay server listening on {self.ip}:{self.port}")
        threading.Thread(target=self.clean_expired_entries, daemon=True).start()

        while self.running.is_set():
            try:
                data, addr = self.sock.recvfrom(self.RECEIVE_BUFFER)

                with self.lock:
                    if addr in self.relay_map:
                        self.forward_packet(data, addr)
                        continue

                try:
                    msg = Message.from_bytes(data)
                    if isinstance(msg, PeerAnnouncement):
                        self.handle_peer_announcement(msg, addr)
                    else:
                        # Might happen during re-connect before both - video
                        # and control - have reconnected
                        logging.debug(f"Unsupported message type from {addr}")
                except Exception:
                    logging.debug(f"Dropped malformed message from {addr}")

            except OSError:
                if not self.running.is_set():
                    break
                logging.error("Socket error")
            except Exception as e:
                logging.error(f"Unhandled error: {e}", exc_info=True)

    def shutdown(self):
        self.running.clear()
        try:
            self.sock.close()
        except Exception as e:
            logging.warning(f"Error closing socket: {e}")
