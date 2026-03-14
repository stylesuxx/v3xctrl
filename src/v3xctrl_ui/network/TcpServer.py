"""
TCP server for direct mode viewer.

Accepts TCP connections from the streamer on video and control ports,
and bridges TCP traffic to local UDP components (video receiver, Server/UDPReceiver).

In direct mode the viewer has the known/fixed IP, so it runs the TCP server
and the streamer connects as a client.

Each channel (video, control) runs independently:
- Video: TCP inbound -> UDP to localhost:videoPort (unidirectional)
- Control: TCP inbound -> UDP to localhost:controlPort, UDP replies -> TCP outbound
"""

import logging
import select
import socket
import threading

from v3xctrl_tcp.framing import recv_message, send_message
from v3xctrl_tcp.keepalive import configure_keepalive
from v3xctrl_tcp.send_timeout import configure_send_timeout

logger = logging.getLogger(__name__)


class TcpServer:
    """TCP server that bridges TCP connections to local UDP components."""

    def __init__(self, video_port: int, control_port: int) -> None:
        self.video_port = video_port
        self.control_port = control_port
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    @property
    def ephemeral_video_port(self) -> int | None:
        """UDP ephemeral port used for video forwarding (E1)."""
        return self._video_udp_port

    @property
    def ephemeral_control_port(self) -> int | None:
        """UDP ephemeral port used for control forwarding (E2)."""
        return self._control_udp_port

    def start(self) -> None:
        self._stop_event.clear()
        self._video_udp_port: int | None = None
        self._control_udp_port: int | None = None

        video_thread = threading.Thread(
            target=self._run_channel,
            args=(self.video_port, False),
            name="TcpServer-video",
            daemon=True,
        )
        control_thread = threading.Thread(
            target=self._run_channel,
            args=(self.control_port, True),
            name="TcpServer-control",
            daemon=True,
        )
        self._threads = [video_thread, control_thread]
        video_thread.start()
        control_thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        for t in self._threads:
            t.join(timeout=2.0)

        self._threads.clear()

    def _run_channel(self, port: int, bidirectional: bool) -> None:
        """Accept loop for a single channel (video or control)."""
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            tcp_sock.bind(("0.0.0.0", port))
            tcp_sock.listen(1)
            tcp_sock.settimeout(1.0)
            channel = "control" if bidirectional else "video"
            logger.info(f"TCP server listening on port {port} ({channel})")

        except OSError:
            logger.error(f"Failed to bind TCP server on port {port}")
            return

        try:
            while not self._stop_event.is_set():
                # Accept a connection (with timeout so we can check stop_event)
                try:
                    client_sock, addr = tcp_sock.accept()
                except TimeoutError:
                    continue

                client_sock.setsockopt(
                    socket.IPPROTO_TCP, socket.TCP_NODELAY, 1
                )
                configure_keepalive(client_sock)
                configure_send_timeout(client_sock, 200)
                logger.info(f"TCP client connected on port {port} from {addr}")

                # Fresh UDP socket per connection so outbound threads from
                # prior (disconnected) connections don't steal UDP replies.
                udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_sock.bind(("127.0.0.1", 0))
                ephemeral_port = udp_sock.getsockname()[1]

                if bidirectional:
                    self._control_udp_port = ephemeral_port
                else:
                    self._video_udp_port = ephemeral_port

                self._handle_connection(
                    client_sock, udp_sock, port, bidirectional
                )

                udp_sock.close()
                logger.info(f"TCP client disconnected on port {port}")

        finally:
            tcp_sock.close()

    def _handle_connection(
        self,
        tcp_sock: socket.socket,
        udp_sock: socket.socket,
        local_port: int,
        bidirectional: bool,
    ) -> None:
        """Handle a single TCP connection, forwarding data to/from UDP."""
        outbound_thread: threading.Thread | None = None

        if bidirectional:
            # Start outbound thread: UDP replies on ephemeral port -> TCP
            outbound_thread = threading.Thread(
                target=self._outbound_loop,
                args=(tcp_sock, udp_sock),
                name=f"TcpServer-out-{local_port}",
                daemon=True,
            )
            outbound_thread.start()

        # Inbound: TCP -> UDP to localhost:local_port
        try:
            while not self._stop_event.is_set():
                # Wait for TCP data with timeout so stop_event can be checked
                readable, _, _ = select.select([tcp_sock], [], [], 1.0)
                if not readable:
                    continue
                data = recv_message(tcp_sock)
                if data is None:
                    break
                udp_sock.sendto(data, ("127.0.0.1", local_port))

        except OSError:
            pass

        finally:
            tcp_sock.close()
            if outbound_thread is not None:
                outbound_thread.join(timeout=2.0)

    def _outbound_loop(
        self,
        tcp_sock: socket.socket,
        udp_sock: socket.socket,
    ) -> None:
        """Read UDP replies on ephemeral port, forward over TCP."""
        try:
            while not self._stop_event.is_set():
                readable, _, _ = select.select([udp_sock], [], [], 1.0)
                if not readable:
                    continue

                data, _addr = udp_sock.recvfrom(65535)
                if not send_message(tcp_sock, data):
                    break

        except (OSError, ValueError):
            pass
