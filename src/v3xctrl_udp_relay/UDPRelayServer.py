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
  PeerInfo,
  Error,
)

from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.PeerRegistry import PeerRegistry
from v3xctrl_udp_relay.PacketRelay import PacketRelay
from v3xctrl_udp_relay.custom_types import Role, PortType, PeerEntry, Session


class UDPRelayServer(threading.Thread):
    TIMEOUT = 3600 // 8
    CLEANUP_INTERVAL = 1
    RECEIVE_BUFFER = 2048
    COMMAND_SOCKET_PATH = "/tmp/udp_relay_command.sock"

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

        # Setup command socket
        self._setup_command_socket()

    def _setup_command_socket(self) -> None:
        """Setup Unix socket for command interface"""
        if os.path.exists(self.COMMAND_SOCKET_PATH):
            os.unlink(self.COMMAND_SOCKET_PATH)

        self.command_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.command_sock.bind(self.COMMAND_SOCKET_PATH)
        self.command_sock.listen(5)

        # Start command handler thread
        threading.Thread(target=self._handle_commands, daemon=True).start()

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

        with self.registry.lock:
            for session_id, session in self.registry.sessions.items():
                mappings: List[Dict[str, Any]] = []

                # Get active addresses for this session from relay
                with self.relay.lock:
                    session_addresses = self.relay.session_to_addresses.get(session_id, set())

                    for addr in session_addresses:
                        if addr in self.relay.relay_map:
                            # Find role and port_type for this address
                            role_info = self._find_role_for_address(session, addr)
                            if role_info:
                                role, port_type = role_info
                                mappings.append({
                                    'address': f"{addr[0]}:{addr[1]}",
                                    'role': role.name,
                                    'port_type': port_type.name
                                })

                result[session_id] = {
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

        # Clean up command socket
        try:
            self.command_sock.close()
            if os.path.exists(self.COMMAND_SOCKET_PATH):
                os.unlink(self.COMMAND_SOCKET_PATH)

        except Exception as e:
            logging.warning(f"Error cleaning up command socket: {e}")