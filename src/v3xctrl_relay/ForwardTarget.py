import logging
import socket
import threading
from abc import ABC, abstractmethod

from v3xctrl_helper import Address
from v3xctrl_tcp.framing import send_message
from v3xctrl_tcp.send_timeout import configure_send_timeout

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
    def __init__(self, tcp_sock: socket.socket) -> None:
        self._sock = tcp_sock
        self._lock = threading.Lock()
        self._alive = True
        configure_send_timeout(tcp_sock, 50)

    def send(self, data: bytes) -> bool:
        with self._lock:
            if not self._alive:
                return False

            if not send_message(self._sock, data):
                self._alive = False
                return False

            return True

    def is_alive(self) -> bool:
        return self._alive

    def close(self) -> None:
        self._alive = False
        try:
            self._sock.close()
        except OSError:
            pass
