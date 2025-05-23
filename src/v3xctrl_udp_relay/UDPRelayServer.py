"""
Simple UDP relay

Sessions are matched based on their ID, each session needs a server and a
client.

Session mapping is kept alive as long as a peer keeps re-announcing or active
communication is happening over either of the ports.

Relay mappings are removed after a certain time of inactivity and allow to be
re-established if the peer shows up again.
"""

import logging
import socket
import threading
import time

from v3xctrl_control.Message import Message, PeerAnnouncement, PeerInfo


class PeerEntry:
    def __init__(self, addr):
        self.addr = addr
        self.ts = time.time()


class Session:
    def __init__(self):
        self.roles = {"client": {}, "server": {}}

    def register(self, role, port_type, addr):
        self.roles[role][port_type] = PeerEntry(addr)

    def is_ready(self, role, valid_types):
        for port_type in valid_types:
            if port_type not in self.roles[role]:
                return False

        return True

    def get_peer(self, role, port_type):
        return self.roles[role].get(port_type)


class UDPRelayServer(threading.Thread):
    TIMEOUT = 10
    CLEANUP_INTERVAL = 5
    RECEIVE_BUFFER = 2048
    VALID_TYPES = ["video", "control"]
    VALID_ROLES = ["client", "server"]

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

    def clean_expired_entries(self):
        while self.running.is_set():
            now = time.time()
            with self.lock:
                role_expiry_map = {}
                for addr, entry in list(self.relay_map.items()):
                    session_id = entry["session"]
                    role = entry["role"]
                    port_type = entry["port_type"]
                    expired = now - entry["ts"] > self.TIMEOUT
                    role_expiry_map.setdefault((session_id, role), {})[port_type] = expired

                for (session_id, role), port_expiry in role_expiry_map.items():
                    if all(port_expiry.get(pt, False) for pt in self.VALID_TYPES):
                        for addr, entry in list(self.relay_map.items()):
                            if entry["session"] == session_id and entry["role"] == role:
                                del self.relay_map[addr]
                                logging.debug(f"Expired mapping for {session_id}:{role}:{entry['port_type']} at {addr}")
                        if session_id in self.sessions:
                            self.sessions[session_id].roles[role] = {}
                            logging.debug(f"Removed expired role {role} from session {session_id}")

                for sid, session in list(self.sessions.items()):
                    all_expired = True
                    any_in_relay = False
                    for role_dict in session.roles.values():
                        for peer in role_dict.values():
                            if now - peer.ts <= self.TIMEOUT:
                                all_expired = False
                            if peer.addr in self.relay_map:
                                any_in_relay = True

                    if all_expired and not any_in_relay:
                        del self.sessions[sid]
                        logging.info(f"Removed expired session: {sid}")

            time.sleep(self.CLEANUP_INTERVAL)

    def handle_peer_announcement(self, msg: PeerAnnouncement, addr):
        session_id = msg.get_id()
        role = msg.get_role()
        port_type = msg.get_port_type()
        other_role = "server" if role == "client" else "client"

        if role not in self.VALID_ROLES or port_type not in self.VALID_TYPES:
            logging.warning(f"Invalid announcement from {addr} — role={role}, port_type={port_type}")
            return

        now = time.time()
        with self.lock:
            session = self.sessions.setdefault(session_id, Session())
            session.register(role, port_type, addr)

            logging.info(f"Registered {role.upper()} {port_type} for session '{session_id}' from {addr}")
            if session.is_ready(role, self.VALID_TYPES) and session.is_ready(other_role, self.VALID_TYPES):
                is_first_time = True
                for pt in self.VALID_TYPES:
                    client = session.get_peer("client", pt)
                    server = session.get_peer("server", pt)
                    if not client or not server:
                        continue

                    if client.addr in self.relay_map or server.addr in self.relay_map:
                        is_first_time = False

                    self.relay_map[client.addr] = {
                        "target": server.addr,
                        "ts": now,
                        "session": session_id,
                        "role": "client",
                        "port_type": pt
                    }
                    self.relay_map[server.addr] = {
                        "target": client.addr,
                        "ts": now,
                        "session": session_id,
                        "role": "server",
                        "port_type": pt
                    }

                try:
                    peer_info = PeerInfo(ip=self.ip, video_port=self.port, control_port=self.port)

                    if is_first_time:
                        for pt in self.VALID_TYPES:
                            self.sock.sendto(peer_info.to_bytes(), session.get_peer("client", pt).addr)
                            self.sock.sendto(peer_info.to_bytes(), session.get_peer("server", pt).addr)
                    else:
                        for pt in self.VALID_TYPES:
                            peer = session.get_peer(role, pt)
                            if peer:
                                self.sock.sendto(peer_info.to_bytes(), peer.addr)

                except Exception as e:
                    logging.error(f"Error sending PeerInfo: {e}", exc_info=True)

                logging.info(f"Relay mapping and PeerInfo update complete for session '{session_id}'")

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
                        logging.info(f"Unsupported message type from {addr}")
                except Exception:
                    logging.info(f"Dropped malformed message from {addr}")

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
