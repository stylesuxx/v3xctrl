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

    def _is_role_ready(self, session: dict, role: str) -> bool:
        for port_type in self.VALID_TYPES:
            if port_type not in session.get(role, {}):
                return False

        return True

    def clean_expired_entries(self):
        logging.info("Started cleanup thread")
        while self.running.is_set():
            now = time.time()
            with self.lock:
                # Track expiry per (session, role)
                role_expiry_map = {}  # (session_id, role) -> {port_type: expired_bool}
                for addr, entry in list(self.relay_map.items()):
                    session_id = entry["session"]
                    role = entry["role"]
                    port_type = entry["port_type"]

                    expired = now - entry["ts"] > self.TIMEOUT
                    key = (session_id, role)

                    if key not in role_expiry_map:
                        role_expiry_map[key] = {}

                    role_expiry_map[key][port_type] = expired

                logging.info(role_expiry_map)

                # Expire full role if ALL port types have expired
                for (session_id, role), port_expiry in role_expiry_map.items():
                    if all(port_expiry.get(pt, False) for pt in self.VALID_TYPES):
                        for addr, entry in list(self.relay_map.items()):
                            if (
                                entry["session"] == session_id and
                                entry["role"] == role and
                                entry["port_type"] in self.VALID_TYPES
                            ):
                                del self.relay_map[addr]
                                logging.debug(f"Expired mapping for {session_id}:{role}:{entry['port_type']} at {addr}")

                        # Also remove the expired role from the session
                        if session_id in self.sessions:
                            session = self.sessions[session_id]
                            if role in session:
                                del session[role]
                                logging.debug(f"Removed expired role {role} from session {session_id}")

                # Clean up sessions if completely expired
                for sid, peers in list(self.sessions.items()):
                    all_expired = True
                    any_in_relay = False

                    for role_dict in peers.values():
                        for entry in role_dict.values():
                            if now - entry["ts"] <= self.TIMEOUT:
                                all_expired = False
                            if entry["addr"] in self.relay_map:
                                any_in_relay = True

                    if all_expired and not any_in_relay:
                        del self.sessions[sid]
                        logging.info(f"Removed expired session: {sid}")

            time.sleep(self.CLEANUP_INTERVAL)

    def handle_peer_announcement(self, msg: PeerAnnouncement, addr):
        session_id = msg.get_id()
        role = msg.get_role()
        port_type = msg.get_port_type()

        if role not in self.VALID_ROLES or port_type not in self.VALID_TYPES:
            logging.warning(f"Invalid announcement from {addr} — role={role}, port_type={port_type}")
            return

        now = time.time()
        with self.lock:
            session = self.sessions.setdefault(session_id, {})
            role_entry = session.setdefault(role, {})
            role_entry[port_type] = {"addr": addr, "ts": now}
            other_role = "server" if role == "client" else "client"

            logging.info(f"Registered {role.upper()} {port_type} for session '{session_id}' from {addr}")
            if other_role in session:
                role_ready = self._is_role_ready(session, role)
                other_ready = self._is_role_ready(session, other_role)

                if role_ready and other_ready:
                    client = session["client"]
                    server = session["server"]

                    is_first_time = True
                    for port_type in self.VALID_TYPES:
                        client_addr = client[port_type]["addr"]
                        server_addr = server[port_type]["addr"]
                        if (
                            client_addr in self.relay_map or
                            server_addr in self.relay_map
                        ):
                            is_first_time = False

                        self.relay_map[client_addr] = {
                            "target": server_addr,
                            "ts": now,
                            "session": session_id,
                            "role": "client",
                            "port_type": port_type
                        }
                        self.relay_map[server_addr] = {
                            "target": client_addr,
                            "ts": now,
                            "session": session_id,
                            "role": "server",
                            "port_type": port_type
                        }

                    try:
                        peer_info = PeerInfo(ip=self.ip, video_port=self.port, control_port=self.port)

                        if is_first_time:
                            # Initial session establishment: notify both sides
                            for port_type in self.VALID_TYPES:
                                self.sock.sendto(peer_info.to_bytes(), client[port_type]["addr"])
                                self.sock.sendto(peer_info.to_bytes(), server[port_type]["addr"])
                        else:
                            # Reconnect: notify only the re-announcing peer
                            for port_type in self.VALID_TYPES:
                                peer_addr = session[role].get(port_type, {}).get("addr")
                                if peer_addr:
                                    self.sock.sendto(peer_info.to_bytes(), peer_addr)

                    except Exception as e:
                        logging.error(f"Error sending PeerInfo: {e}")

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
                logging.error("Socket error", exc_info=True)
            except Exception as e:
                logging.error(f"Unhandled error: {e}")

    def shutdown(self):
        self.running.clear()
        try:
            self.sock.close()
        except Exception as e:
            logging.warning(f"Error closing socket: {e}")
