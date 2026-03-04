from __future__ import annotations

import logging
import select
import socket
import threading
from typing import TYPE_CHECKING

from v3xctrl_control.message import Message, PeerAnnouncement
from v3xctrl_helper import Address
from v3xctrl_tcp.framing import recv_message
from v3xctrl_tcp.keepalive import configure_keepalive
from v3xctrl_udp_relay.ForwardTarget import TcpTarget
from v3xctrl_udp_relay.Role import Role
from v3xctrl_udp_relay.custom_types import PortType

if TYPE_CHECKING:
    from v3xctrl_udp_relay.PacketRelay import PacketRelay

logger = logging.getLogger(__name__)


class TCPAcceptor:
    def __init__(self, port: int, relay: PacketRelay, stop_event: threading.Event) -> None:
        self.port = port
        self.relay = relay
        self.stop_event = stop_event
        self._listener: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._accept_loop,
            name="TCPAcceptor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._listener:
            try:
                self._listener.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=5.0)

    def _accept_loop(self) -> None:
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.settimeout(1.0)
        self._listener.bind(("0.0.0.0", self.port))
        self._listener.listen(16)

        logger.info(f"TCPAcceptor listening on port {self.port}")

        while not self.stop_event.is_set():
            try:
                tcp_sock, addr = self._listener.accept()
                threading.Thread(
                    target=self._handle_connection,
                    args=(tcp_sock, addr),
                    name=f"TCPAcceptor-conn-{addr}",
                    daemon=True,
                ).start()

            except socket.timeout:
                continue

            except OSError:
                if not self.stop_event.is_set():
                    logger.error("TCPAcceptor accept error", exc_info=True)
                break

    def _handle_connection(self, tcp_sock: socket.socket, addr: Address) -> None:
        tcp_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        configure_keepalive(tcp_sock)
        target = TcpTarget(tcp_sock)

        try:
            # Read handshake (PeerAnnouncement)
            data = recv_message(tcp_sock)
            if data is None:
                logger.warning(f"TCPAcceptor: no handshake from {addr}")
                return

            msg = Message.from_bytes(data)
            if not isinstance(msg, PeerAnnouncement):
                logger.warning(f"TCPAcceptor: expected PeerAnnouncement, got {msg.type} from {addr}")
                return

            port_type = PortType(msg.get_port_type())
            logger.info(f"TCPAcceptor: {msg.get_role()} connected for {port_type.name} from {addr}")

            # Register with relay (sends PeerInfo response via TcpTarget)
            self.relay.register_tcp_peer(msg, addr, target)

            # Behavior depends on port type and role
            if port_type == PortType.VIDEO:
                role = Role(msg.get_role())
                if role == Role.STREAMER:
                    self._read_and_forward_loop(tcp_sock, addr)
                else:
                    self._monitor_disconnect(tcp_sock)
            elif port_type == PortType.CONTROL:
                self._read_and_forward_loop(tcp_sock, addr)

        except Exception:
            logger.error(f"TCPAcceptor: error handling {addr}", exc_info=True)

        finally:
            self.relay.unregister_tcp_peer(addr)
            target.close()

    def _monitor_disconnect(self, tcp_sock: socket.socket) -> None:
        """Video connections: relay only sends TO viewer. Monitor for disconnect.

        Uses select() for timeout instead of settimeout() so the socket stays
        in blocking mode — TcpTarget.send() (sendall) on the same socket must
        never be subject to a recv timeout.
        """
        while not self.stop_event.is_set():
            try:
                readable, _, _ = select.select([tcp_sock], [], [], 5.0)
                if not readable:
                    continue

                data = tcp_sock.recv(1)
                if not data:
                    break

            except (OSError, ValueError):
                break

    def _read_and_forward_loop(self, tcp_sock: socket.socket, addr: Address) -> None:
        """Read framed messages from a TCP peer and forward via relay."""
        try:
            while not self.stop_event.is_set():
                data = recv_message(tcp_sock)
                if data is None:
                    break

                self.relay.forward_packet(data, addr)

        except OSError:
            pass
