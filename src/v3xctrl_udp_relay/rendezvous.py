import logging
import socket
import threading
import time

from rpi_4g_streamer.Message import Message, PeerAnnouncement, PeerInfo


class UDPRelayServer:
    RELAY_PUBLIC_IP = ""
    PORT = 8888
    TIMEOUT = 10
    CLEANUP_INTERVAL = 5
    VALID_TYPES = ["video", "control"]
    ROLES = ["client", "server"]

    def __init__(self):
        self.sessions = {}    # session_id -> role -> port_type -> {"addr": (ip, port), "ts": float}
        self.relay_map = {}   # (ip, port) -> {"target": (ip, port), "ts": float}
        self.lock = threading.Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', self.PORT))

    def clean_expired_entries(self):
        while True:
            now = time.time()
            with self.lock:
                expired_keys = [
                    key for key, values in self.relay_map.items()
                    if now - values["ts"] > self.TIMEOUT
                ]
                for key in expired_keys:
                    logging.info(f"Removed expired relay entry: {key}")
                    del self.relay_map[key]

                expired_sids = [
                    sid for sid, peers in self.sessions.items()
                    if all(
                        now - entry["ts"] > self.TIMEOUT
                        for role in peers.values()
                        for entry in role.values()
                    )
                ]
                for sid in expired_sids:
                    logging.info(f"Removed expired session: {sid}")
                    del self.sessions[sid]

            time.sleep(self.CLEANUP_INTERVAL)

    def handle_peer_announcement(self, msg: PeerAnnouncement, addr):
        session_id = msg.get_id()
        role = msg.get_role()
        port_type = msg.get_port_type()

        if role not in self.ROLES or port_type not in self.VALID_TYPES:
            logging.warning(f"Invalid announcement from {addr} — role={role}, port_type={port_type}")
            return

        with self.lock:
            session = self.sessions.setdefault(session_id, {})
            role_entry = session.setdefault(role, {})
            role_entry[port_type] = {"addr": addr, "ts": time.time()}

            logging.info(f"Registered {role.upper()} {port_type} for session '{session_id}' from {addr}")

            if all(
                r in session and all(pt in session[r] for pt in self.VALID_TYPES)
                for r in self.ROLES
            ):
                client = session["client"]
                server = session["server"]

                for pt in self.VALID_TYPES:
                    client_addr = client[pt]["addr"]
                    server_addr = server[pt]["addr"]

                    self.relay_map[client_addr] = {
                        "target": server_addr,
                        "ts": time.time()
                    }
                    self.relay_map[server_addr] = {
                        "target": client_addr,
                        "ts": time.time()
                    }

                try:
                    relay_ip = self.RELAY_PUBLIC_IP
                    relay_port = self.PORT

                    peer_info = PeerInfo(
                        ip=relay_ip,
                        video_port=relay_port,
                        control_port=relay_port,
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
        logging.info(f"UDP Relay server listening on port {self.PORT}")
        threading.Thread(target=self.clean_expired_entries, daemon=True).start()

        while True:
            try:
                data, addr = self.sock.recvfrom(2048)

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

            except Exception as e:
                logging.error(f"Error: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = UDPRelayServer()
    server.run()
