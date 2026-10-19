import contextlib
import logging
import queue
import socket
import threading
from abc import ABC, abstractmethod

from v3xctrl_helper import Address
from v3xctrl_tcp.framing import send_message
from v3xctrl_tcp.send_timeout import STREAM_SEND_TIMEOUT_MS, configure_send_timeout

logger = logging.getLogger(__name__)


class ForwardTarget(ABC):
    @abstractmethod
    def send(self, data: bytes) -> bool: ...

    @abstractmethod
    def is_alive(self) -> bool: ...


class UdpTarget(ForwardTarget):
    def __init__(self, sock: socket.socket, addr: Address) -> None:
        self._sock = sock
        self._addr = addr

    def send(self, data: bytes) -> bool:
        try:
            self._sock.sendto(data, self._addr)
            return True

        except OSError:
            return False

    def is_alive(self) -> bool:
        return True


class TcpTarget(ForwardTarget):
    """Sends length-prefixed frames on a TCP connection from its own thread.

    `send` only queues, so the relay's receive loop never waits on a slow
    peer, and one sender per connection keeps the frames in the order they
    were queued. A send that blocks past the send timeout leaves a half-written
    frame behind, so the connection is shut down and the peer reconnects.
    """

    # 1.4 MB of 1400 byte RTP packets: six seconds of video at the default
    # 1.8 Mbit/s, on top of the kernel send buffer. A peer that falls further
    # behind loses packets until its queue drains.
    QUEUE_SIZE = 1024

    def __init__(self, tcp_sock: socket.socket, send_timeout_ms: int = STREAM_SEND_TIMEOUT_MS) -> None:
        self._sock = tcp_sock
        self._queue: queue.Queue[bytes | None] = queue.Queue(maxsize=self.QUEUE_SIZE)
        self._alive = True
        self._dropped_packets = 0
        self._peer = self._describe_peer(tcp_sock)
        configure_send_timeout(tcp_sock, send_timeout_ms)

        self._sender = threading.Thread(target=self._send_loop, name=f"TcpTarget-{self._peer}", daemon=True)
        self._sender.start()

    @staticmethod
    def _describe_peer(tcp_sock: socket.socket) -> str:
        try:
            return str(tcp_sock.getpeername())

        except OSError:
            return "unknown peer"

    def send(self, data: bytes) -> bool:
        if not self._alive:
            return False

        try:
            self._queue.put_nowait(data)

        except queue.Full:
            self._dropped_packets += 1
            if self._dropped_packets == 1:
                logger.warning(f"TCP target {self._peer}: send queue full, dropping packets")

            return False

        if self._dropped_packets > 0:
            logger.warning(
                f"TCP target {self._peer}: send queue drained after dropping {self._dropped_packets} packets"
            )
            self._dropped_packets = 0

        return True

    def _send_loop(self) -> None:
        while self._alive:
            data = self._queue.get()
            if data is None:
                return

            if not send_message(self._sock, data):
                if self._alive:
                    logger.warning(f"TCP target {self._peer}: send failed or timed out, closing the connection")
                    self._alive = False
                    with contextlib.suppress(OSError):
                        self._sock.shutdown(socket.SHUT_RDWR)

                return

    def is_alive(self) -> bool:
        return self._alive

    def close(self) -> None:
        self._alive = False

        with contextlib.suppress(queue.Full):
            self._queue.put_nowait(None)

        with contextlib.suppress(OSError):
            self._sock.close()
