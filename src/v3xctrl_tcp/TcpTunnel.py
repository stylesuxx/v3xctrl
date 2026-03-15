"""
Generic TCP tunnel client - bridges a local UDP component to a remote TCP endpoint.

Used by the streamer (both video and control processes) in direct mode and by
both viewer and streamer in relay mode. The only difference is the remote
endpoint (viewer IP vs. relay IP) and whether a handshake is needed.

UDP proxy model:
- Binds a UDP socket on an ephemeral port E
- Outbound: local component sends to localhost:E -> proxy reads -> forwards over TCP
- Inbound: TCP data -> proxy sends from E to localhost:local_component_port
- Responses: component replies to localhost:E -> proxy reads -> forwards over TCP
"""

import logging
import select
import socket
import threading
import time

from v3xctrl_tcp.framing import recv_message, send_message
from v3xctrl_tcp.keepalive import configure_keepalive
from v3xctrl_tcp.send_timeout import configure_send_timeout

logger = logging.getLogger(__name__)

# Retry backoff sequence (seconds)
_RETRY_DELAYS = [1.0, 2.0, 5.0]
_CONNECT_WARN_TIMEOUT = 30.0


class TcpTunnel:
    """TCP tunnel client that bridges local UDP to a remote TCP endpoint."""

    def __init__(
        self,
        remote_host: str,
        remote_port: int,
        local_component_port: int,
        bidirectional: bool = True,
        handshake: bytes | None = None,
    ) -> None:
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.local_component_port = local_component_port
        self.bidirectional = bidirectional
        self.handshake = handshake

        self._stop_event = threading.Event()
        self._ephemeral_port: int | None = None
        self._port_ready = threading.Event()
        self._threads: list[threading.Thread] = []

    @property
    def ephemeral_port(self) -> int | None:
        """The UDP ephemeral port local components should send to."""
        return self._ephemeral_port

    def wait_for_port(self, timeout: float = 5.0) -> int | None:
        """Block until the ephemeral port is allocated. Returns the port."""
        self._port_ready.wait(timeout=timeout)
        return self._ephemeral_port

    def start(self) -> None:
        self._stop_event.clear()
        self._port_ready.clear()

        main_thread = threading.Thread(
            target=self._run,
            name=f"TcpTunnel-{self.remote_host}:{self.remote_port}",
            daemon=True,
        )
        self._threads = [main_thread]
        main_thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        for t in self._threads:
            t.join(timeout=5.0)

        self._threads.clear()

    def _run(self) -> None:
        """Main loop: bind UDP, connect TCP with retry, bridge traffic."""
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.bind(("127.0.0.1", 0))
        self._ephemeral_port = udp_sock.getsockname()[1]
        self._port_ready.set()

        logger.info(f"TcpTunnel UDP proxy bound on ephemeral port {self._ephemeral_port}")

        try:
            while not self._stop_event.is_set():
                tcp_sock = self._connect_with_retry()
                if tcp_sock is None:
                    break  # stop was requested

                if self.handshake is not None and not self._do_handshake(tcp_sock):
                    tcp_sock.close()
                    continue  # retry connection

                logger.info(f"TcpTunnel connected to {self.remote_host}:{self.remote_port}")

                self._bridge(tcp_sock, udp_sock)

                tcp_sock.close()
                if not self._stop_event.is_set():
                    logger.warning(
                        f"TcpTunnel disconnected from {self.remote_host}:{self.remote_port}, reconnecting..."
                    )
        finally:
            udp_sock.close()

    def _connect_with_retry(self) -> socket.socket | None:
        """Try to connect TCP with backoff. Returns socket or None if stopped."""
        attempt = 0
        first_attempt_time = time.monotonic()
        warned = False

        while not self._stop_event.is_set():
            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_sock.settimeout(5.0)

            try:
                tcp_sock.connect((self.remote_host, self.remote_port))
                tcp_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                configure_keepalive(tcp_sock)
                configure_send_timeout(tcp_sock, 200)
                tcp_sock.settimeout(None)
                return tcp_sock

            except OSError as e:
                tcp_sock.close()
                elapsed = time.monotonic() - first_attempt_time

                if not warned and elapsed >= _CONNECT_WARN_TIMEOUT:
                    logger.error(
                        f"Cannot establish TCP connection to "
                        f"{self.remote_host}:{self.remote_port} after "
                        f"{elapsed:.0f}s - is the remote side configured "
                        f"for TCP?"
                    )
                    warned = True

                delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                logger.debug(f"TCP connect failed ({e}), retrying in {delay}s...")

                # Sleep in small increments to check stop_event
                deadline = time.monotonic() + delay
                while time.monotonic() < deadline:
                    if self._stop_event.is_set():
                        return None
                    time.sleep(0.1)

                attempt += 1

        return None

    def _do_handshake(self, tcp_sock: socket.socket) -> bool:
        """Send handshake and read response. Returns True on success."""
        assert self.handshake is not None

        if not send_message(tcp_sock, self.handshake):
            logger.error("TcpTunnel handshake send failed")
            return False

        response = recv_message(tcp_sock)
        if response is None:
            logger.error("TcpTunnel handshake response failed (disconnected)")
            return False

        logger.info(f"TcpTunnel handshake complete ({len(response)} bytes)")
        return True

    def _bridge(
        self,
        tcp_sock: socket.socket,
        udp_sock: socket.socket,
    ) -> None:
        """Bridge traffic between TCP and local UDP until disconnect."""
        inbound_thread: threading.Thread | None = None

        if self.bidirectional:
            # Inbound: TCP -> UDP to localhost:local_component_port
            inbound_thread = threading.Thread(
                target=self._inbound_loop,
                args=(tcp_sock, udp_sock),
                name=f"TcpTunnel-in-{self.remote_port}",
                daemon=True,
            )
            inbound_thread.start()

        # Outbound: UDP on ephemeral port -> TCP
        # In unidirectional mode, also watch tcp_sock for disconnect detection
        # (in bidirectional mode, the inbound thread handles that).
        watch_fds = [udp_sock, tcp_sock] if not self.bidirectional else [udp_sock]
        try:
            while not self._stop_event.is_set():
                readable, _, _ = select.select(watch_fds, [], [], 1.0)
                if not readable:
                    continue

                if tcp_sock in readable:
                    # TCP readable in unidirectional = EOF (no data expected)
                    try:
                        peek = tcp_sock.recv(1, socket.MSG_PEEK)
                        if not peek:
                            break  # remote disconnected
                    except OSError:
                        break

                if udp_sock in readable:
                    try:
                        data, _addr = udp_sock.recvfrom(65535)
                    except OSError:
                        break

                    if not send_message(tcp_sock, data):
                        break
        except OSError:
            pass

        finally:
            tcp_sock.close()
            if inbound_thread is not None:
                inbound_thread.join(timeout=2.0)

    def _inbound_loop(
        self,
        tcp_sock: socket.socket,
        udp_sock: socket.socket,
    ) -> None:
        """Read TCP data, forward as UDP to localhost:local_component_port."""
        try:
            while not self._stop_event.is_set():
                readable, _, _ = select.select([tcp_sock], [], [], 1.0)
                if not readable:
                    continue

                data = recv_message(tcp_sock)
                if data is None:
                    break

                udp_sock.sendto(data, ("127.0.0.1", self.local_component_port))

        except OSError:
            pass
