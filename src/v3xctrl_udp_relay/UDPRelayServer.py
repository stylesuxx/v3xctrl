from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
import socket
import threading
import time
from typing import Dict, Optional, Tuple, Any, List

from v3xctrl_helper import Address
from v3xctrl_control.message import (
    Message,
    PeerAnnouncement,
)

from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.PacketRelay import PacketRelay
from v3xctrl_udp_relay.custom_types import Role, PortType, Session


class UDPRelayServer(threading.Thread):
    TIMEOUT = 3600 // 8
    CLEANUP_INTERVAL = 10
    RECEIVE_BUFFER = 2048

    def __init__(
            self,
            ip: str,
            port: int,
            db_path: str,
            command_socket_path: str = "/tmp/udp_relay_command.sock"
    ) -> None:
        super().__init__(daemon=True, name="UDPRelayServer")

        self.ip = ip
        self.port = port
        self.command_socket_path = command_socket_path

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', self.port))

        self.relay = PacketRelay(
            SessionStore(db_path),
            self.sock,
            (self.ip, self.port),
            self.TIMEOUT
        )

        self.executor = ThreadPoolExecutor(max_workers=10)
        self.running = threading.Event()

        self._setup_command_socket()

    def start(self) -> None:
        self.running.set()
        threading.Thread(target=self._cleanup_expired_entries, daemon=True).start()
        threading.Thread(target=self._handle_commands, daemon=True).start()
        super().start()

    def run(self) -> None:
        logging.info(f"UDP Relay server listening on {self.ip}:{self.port}")

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
        self.executor.shutdown(wait=True)

        try:
            self.sock.close()
        except Exception as e:
            logging.warning(f"Error closing socket: {e}")

        try:
            if hasattr(self, 'command_sock'):
                self.command_sock.close()
            if os.path.exists(self.command_socket_path):
                os.unlink(self.command_socket_path)
        except Exception as e:
            logging.warning(f"Error cleaning up command socket: {e}")

        if self.is_alive():
            self.join(timeout=5.0)

    def _setup_command_socket(self) -> None:
        """Setup Unix socket for command interface"""
        if os.path.exists(self.command_socket_path):
            os.unlink(self.command_socket_path)

        self.command_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.command_sock.bind(self.command_socket_path)
        self.command_sock.listen(5)

    def _handle_commands(self) -> None:
        """Handle incoming command socket connections"""
        while self.running.is_set():
            try:
                client_sock, _ = self.command_sock.accept()
                threading.Thread(
                    target=self._process_command,
                    args=(client_sock,),
                    daemon=True
                ).start()
            except OSError:
                if not self.running.is_set():
                    break
            except Exception as e:
                logging.error(f"Command socket error: {e}")

    def _process_command(self, client_sock: socket.socket) -> None:
        """Process individual command connection"""
        try:
            data = client_sock.recv(1024).decode('utf-8').strip()

            if data == "stats":
                stats = self._get_session_stats()
                response = json.dumps(stats, indent=2)
                client_sock.send(response.encode('utf-8'))
            else:
                client_sock.send(b"Unknown command")

        except Exception as e:
            logging.error(f"Error processing command: {e}")
        finally:
            client_sock.close()

    def _get_session_stats(self) -> Dict[str, Dict[str, Any]]:
        """Return current session statistics"""
        result: Dict[str, Dict[str, Any]] = {}

        with self.relay.lock:
            for sid, session in self.relay.sessions.items():
                mappings: List[Dict[str, Any]] = []

                if session:
                    for addr in session.addresses:
                        if addr in self.relay.mappings:
                            role_info = self._find_role_for_address(session, addr)
                            if role_info:
                                role, port_type = role_info
                                mappings.append({
                                    'address': f"{addr[0]}:{addr[1]}",
                                    'role': role.name,
                                    'port_type': port_type.name
                                })

                    result[sid] = {
                        'created_at': session.created_at,
                        'mappings': mappings
                    }

        return result

    def _find_role_for_address(self, session: Session, addr: Address) -> Optional[Tuple[Role, PortType]]:
        """Find role and port_type for given address in session"""
        for role, port_dict in session.roles.items():
            for port_type, peer_entry in port_dict.items():
                if peer_entry.addr == addr:
                    return role, port_type
        return None

    def _handle_peer_announcement(
        self,
        msg: PeerAnnouncement,
        addr: Address
    ) -> None:
        self.relay.register_peer(msg, addr)

    def _cleanup_expired_entries(self) -> None:
        while self.running.is_set():
            self.relay.cleanup_expired_mappings()
            time.sleep(self.CLEANUP_INTERVAL)

    def _handle_packet(self, data: bytes, addr: Address) -> None:
        """
        Main priority is to forward packets as quickly as possible and handle
        peer announcements.
        """
        try:
            if data.startswith(b'\x83\xa1t\xb0PeerAnnouncement'):
                try:
                    msg = Message.from_bytes(data)
                    if isinstance(msg, PeerAnnouncement):
                        self._handle_peer_announcement(msg, addr)
                        return
                except Exception:
                    return

            self.relay.forward_packet(data, addr)

        except Exception as e:
            logging.error(f"Error handling packet from {addr}: {e}", exc_info=True)
