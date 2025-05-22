import logging
import socket
import threading
import time

from rpi_4g_streamer.Message import Message, PeerAnnouncement, PeerInfo


class UDPRelayServer(threading.Thread):
    TIMEOUT = 60
    CLEANUP_INTERVAL = 5
    RECEIVE_BUFFER = 2048
    VALID_TYPES = ["video", "control"]
    VALID_ROLES = ["client", "server"]

    def __init__(self, ip: str, port: int):
        super().__init__(daemon=True)
        self.ip = ip
        self.port = port

        self.running = threading.Event()
        self.running.set()

        self.sessions = {}
        self.relay_map = {}
        self.lock = threading.Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', self.port))

    def clean_expired_entries(self):
        while self.running.is_set():
            now = time.time()
            with self.lock:
                # Check for expired mappings
                for key, values in list(self.relay_map.items()):
                    if now - values["ts"] > self.TIMEOUT:
                        logging.info(f"Removed expired mapping: {key}")
                        del self.relay_map[key]

                # Check for expired sessions
                for sid, peers in self.sessions.items():
                    expired = True
                    for role in peers.values():
                        for entry in role.values():
                            if now - entry["ts"] <= self.TIMEOUT:
                                expired = False
                    if expired:
                        logging.info(f"Removed expired session: {sid}")
                        del self.sessions[sid]

            time.sleep(self.CLEANUP_INTERVAL)

    def handle_peer_announcement(self, msg: PeerAnnouncement, addr):
        session_id = msg.get_id()
        role = msg.get_role()
        port_type = msg.get_port_type()

        if role not in self.VALID_ROLES or port_type not in self.VALID_TYPES:
            logging.warning(f"Invalid announcement from {addr} — role={role}, port_type={port_type}")
            return

        with self.lock:
            session = self.sessions.setdefault(session_id, {})
            role_entry = session.setdefault(role, {})
            role_entry[port_type] = {"addr": addr, "ts": time.time()}

            logging.info(f"Registered {role.upper()} {port_type} for session '{session_id}' from {addr}")

            if all(
                r in session and all(pt in session[r] for pt in self.VALID_TYPES)
                for r in self.VALID_ROLES
            ):
                client = session["client"]
                server = session["server"]

                for pt in self.VALID_TYPES:
                    self.relay_map[client[pt]["addr"]] = {
                        "target": server[pt]["addr"],
                        "ts": time.time()
                    }
                    self.relay_map[server[pt]["addr"]] = {
                        "target": client[pt]["addr"],
                        "ts": time.time()
                    }

                try:
                    peer_info = PeerInfo(
                        ip=self.ip,
                        video_port=self.port,
                        control_port=self.port,
                    )
                    for pt in self.VALID_TYPES:
                        self.sock.sendto(peer_info.to_bytes(), client[pt]["addr"])
                        self.sock.sendto(peer_info.to_bytes(), server[pt]["addr"])
                except Exception as e:
                    logging.error(f"Error sending PeerInfo: {e}")

                logging.info(f"Relay mapping and PeerInfo exchange complete for session '{session_id}'")
                del self.sessions[session_id]

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
