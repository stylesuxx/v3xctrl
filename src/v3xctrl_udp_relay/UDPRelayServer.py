from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
import socket
import threading
import time
from typing import Any

from v3xctrl_helper import Address
from v3xctrl_control.message import (
    Message,
    ConnectionTest,
    ConnectionTestAck,
    PeerAnnouncement,
)

from v3xctrl_udp_relay.SessionStore import SessionStore
from v3xctrl_udp_relay.PacketRelay import PacketRelay
from v3xctrl_udp_relay.TCPAcceptor import TCPAcceptor
from v3xctrl_udp_relay.Role import Role
from v3xctrl_tcp import Transport
from v3xctrl_udp_relay.custom_types import PortType, Session


class UDPRelayServer(threading.Thread):
    TIMEOUT = 3600 // 8
    CLEANUP_INTERVAL = 10
    RECEIVE_BUFFER = 2048

    COMMAND_SOCKET_TEMPLATE = "/tmp/udp_relay_command_{port}.sock"

    def __init__(
            self,
            ip: str,
            port: int,
            db_path: str,
    ) -> None:
        super().__init__(daemon=True, name="UDPRelayServer")

        self.ip = ip
        self.port = port
        self.command_socket_path = self.COMMAND_SOCKET_TEMPLATE.format(port=port)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', self.port))

        self.relay = PacketRelay(
            SessionStore(db_path),
            self.sock,
            (self.ip, self.port),
            self.TIMEOUT
        )

        self.tcp_executor = ThreadPoolExecutor(max_workers=10)
        self.control_executor = ThreadPoolExecutor(max_workers=4)
        self.running = threading.Event()
        self._tcp_stop = threading.Event()
        self.tcp_acceptor = TCPAcceptor(self.port, self.relay, self._tcp_stop)

        self._setup_command_socket()

    def start(self) -> None:
        self.running.set()
        self.tcp_acceptor.start()
        threading.Thread(target=self._cleanup_expired_entries, daemon=True).start()
        threading.Thread(target=self._handle_commands, daemon=True).start()
        super().start()

    def run(self) -> None:
        logging.info(f"UDP Relay server listening on {self.ip}:{self.port}")

        while self.running.is_set():
            try:
                data, addr = self.sock.recvfrom(self.RECEIVE_BUFFER)

                deferred_tcp = self.relay.forward_packet(data, addr)
                if deferred_tcp is not None:
                    for tcp_target in deferred_tcp:
                        self.tcp_executor.submit(tcp_target.send, data)
                else:
                    self.control_executor.submit(self._handle_slow_packet, data, addr)
            except OSError:
                if not self.running.is_set():
                    break
                logging.error("Socket error")
            except Exception as e:
                logging.error(f"Unhandled error: {e}", exc_info=True)

    def shutdown(self) -> None:
        self.running.clear()
        self._tcp_stop.set()
        self.tcp_acceptor.stop()
        self.tcp_executor.shutdown(wait=True)
        self.control_executor.shutdown(wait=True)

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

    def _get_session_stats(self) -> dict[str, dict[str, Any]]:
        """Return current session statistics"""
        now = time.time()
        result: dict[str, dict[str, Any]] = {}

        with self.relay.lock:
            for sid, session in self.relay.sessions.items():
                mappings: list[dict[str, Any]] = []
                spectators: list[dict[str, Any]] = []

                if session:
                    for role, port_dict in session.roles.items():
                        for port_type, peer_entry in port_dict.items():
                            addr = peer_entry.addr
                            timeout_in_sec = 0

                            with self.relay.mapping_lock:
                                mapping = self.relay.mappings.get(addr)
                                if mapping:
                                    diff = now - mapping.timestamp
                                    if diff < self.TIMEOUT:
                                        timeout_in_sec = round(self.TIMEOUT - diff)

                            mappings.append({
                                'address': f"{addr[0]}:{addr[1]}",
                                'role': role.name,
                                'port_type': port_type.name,
                                'timeout_in_sec': timeout_in_sec,
                            })

                    for spectator in session.spectators:
                        timeout_in_sec = 0
                        diff = now - spectator.last_announcement_at
                        if diff < self.relay.SPECTATOR_TIMEOUT:
                            timeout_in_sec = round(self.relay.SPECTATOR_TIMEOUT - diff)

                        for port_type, peer_entry in spectator.ports.items():
                            addr = peer_entry.addr
                            spectators.append({
                                'address': f"{addr[0]}:{addr[1]}",
                                'role': Role.SPECTATOR.name,
                                'port_type': port_type.name,
                                'timeout_in_sec': timeout_in_sec,
                            })

                    result[sid] = {
                        'created_at': session.created_at,
                        'mappings': mappings,
                        'spectators': spectators
                    }

        return result

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

    def _handle_connection_test(self, data: bytes, addr: Address) -> None:
        """Validate session/spectator ID and reply with ConnectionTestAck."""
        try:
            msg = Message.from_bytes(data)
            if not isinstance(msg, ConnectionTest):
                return

            if msg.spectator:
                valid = self.relay.store.get_session_id_from_spectator_id(msg.id) is not None
            else:
                valid = self.relay.store.exists(msg.id)

            ack = ConnectionTestAck(v=valid)
            self.sock.sendto(ack.to_bytes(), addr)
        except Exception as e:
            logging.error(f"Error handling connection test from {addr}: {e}", exc_info=True)

    def _handle_slow_packet(self, data: bytes, addr: Address) -> None:
        """Handle non-data packets: peer announcements, connection tests, spectator heartbeats."""
        try:
            if data.startswith(b'\x83\xa1t\xb0PeerAnnouncement'):
                try:
                    msg = Message.from_bytes(data)
                    if isinstance(msg, PeerAnnouncement):
                        self._handle_peer_announcement(msg, addr)
                        return
                except Exception:
                    return

            if data.startswith(b'\x83\xa1t\xaeConnectionTest'):
                self._handle_connection_test(data, addr)
                return

            self.relay.update_spectator_heartbeat(addr)

        except Exception as e:
            logging.error(f"Error handling packet from {addr}: {e}", exc_info=True)
