from concurrent.futures import ThreadPoolExecutor
import logging
import socket
import threading
import time
from typing import Dict

from v3xctrl_helper import Address
from v3xctrl_control.message import (
  Message,
  PeerAnnouncement,
  PeerInfo,
  Error,
)

from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.PeerRegistry import PeerRegistry
from v3xctrl_udp_relay.PacketRelay import PacketRelay
from v3xctrl_udp_relay.custom_types import Role, PortType, PeerEntry


class UDPRelayServer(threading.Thread):
    TIMEOUT = 3600 // 8
    CLEANUP_INTERVAL = 1
    RECEIVE_BUFFER = 2048

    def __init__(self, ip: str, port: int, db_path: str) -> None:
        super().__init__(daemon=True, name="UDPRelayServer")
        self.ip = ip
        self.port = port

        self.registry = PeerRegistry(SessionStore(db_path), self.TIMEOUT)
        self.relay = PacketRelay(self.TIMEOUT)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', self.port))

        self.executor = ThreadPoolExecutor(max_workers=10)
        self.running = threading.Event()
        self.running.set()

    def _handle_peer_announcement(
        self,
        msg: PeerAnnouncement,
        addr: Address
    ) -> None:
        try:
            role = Role(msg.get_role())
            port_type = PortType(msg.get_port_type())

        except ValueError:
            return

        sid = msg.get_id()
        result = self.registry.register_peer(sid, role, port_type, addr)

        if result.error:
            logging.info(f"Ignoring announcement for unknown session '{sid}' from {addr}")

            try:
                error_msg = Error(str(403))
                self.sock.sendto(error_msg.to_bytes(), addr)

            except Exception as e:
                logging.error(f"Failed to send error message to {addr}: {e}", exc_info=True)

            return

        if result.is_new_peer:
            logging.info(f"{sid}: Registered {role.name}:{port_type.name} from {addr}")

        if result.session_ready:
            peers = self.registry.get_session_peers(sid)
            self.relay.update_mapping(sid, peers)
            self._send_peer_info(peers)

            logging.info(f"{sid}: Session ready, peer info exchanged")

    def _send_peer_info(
        self,
        peers: Dict[Role, Dict[PortType, PeerEntry]]
    ) -> None:
        try:
            peer_info = PeerInfo(ip=self.ip, video_port=self.port, control_port=self.port)
            for role_peers in peers.values():
                for peer in role_peers.values():
                    self.sock.sendto(peer_info.to_bytes(), peer.addr)

        except Exception as e:
            logging.error(f"Error sending PeerInfo: {e}", exc_info=True)

    def _cleanup_expired_entries(self) -> None:
        while self.running.is_set():
            expired_sessions = self.relay.cleanup_expired_mappings()
            self.registry.remove_expired_sessions(expired_sessions)
            time.sleep(self.CLEANUP_INTERVAL)

    def _handle_packet(self, data: bytes, addr: Address) -> None:
        """
        Main priority is to forward packets as quickly as possible and handle
        peer announcements.
        """
        try:
            # Fast and cheap byte comparison to check if we have to go the more
            # time consuming path of handling peer announcements.
            if data.startswith(b'\x83\xa1t\xb0PeerAnnouncement'):
                try:
                    msg = Message.from_bytes(data)
                    if isinstance(msg, PeerAnnouncement):
                        self._handle_peer_announcement(msg, addr)
                        return

                except Exception:
                    return

            self.relay.forward_packet(self.sock, data, addr)

        except Exception as e:
            logging.error(f"Error handling packet from {addr}: {e}", exc_info=True)

    def run(self) -> None:
        logging.info(f"UDP Relay server listening on {self.ip}:{self.port}")
        threading.Thread(target=self._cleanup_expired_entries, daemon=True).start()

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
        self.running.clear()
        try:
            self.sock.close()
        except Exception as e:
            logging.warning(f"Error closing socket: {e}")
