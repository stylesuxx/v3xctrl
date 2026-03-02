import logging
import select
import socket
import threading
import time
from typing import Optional, Tuple

from v3xctrl_control.message import Heartbeat

HEARTBEAT_INTERVAL_S = 30.0
RECV_BUFFER_SIZE = 65535


class UdpVideoProxy(threading.Thread):
    """
    UDP proxy that sits between the real video port and ffmpeg's internal
    socket.

    Receives RTP packets on the real video port and forwards them to a local
    port where ffmpeg listens. Sends periodic heartbeats from the real video
    port to the relay to keep the NAT mapping alive.
    """

    def __init__(
        self,
        video_port: int,
        relay_address: Tuple[str, int],
    ) -> None:
        super().__init__(daemon=True)
        self.video_port = video_port
        self.relay_address = relay_address
        self._running = threading.Event()
        self._external_sock: Optional[socket.socket] = None
        self._forward_sock: Optional[socket.socket] = None
        self.local_port: int = 0

    def start_proxy(self) -> bool:
        """Bind the external socket and find a free local port.

        Returns True on success, False if the socket could not be bound.
        Must be called before start().
        """
        try:
            self._external_sock = socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM
            )
            self._external_sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )
            self._external_sock.bind(("0.0.0.0", self.video_port))
            self._external_sock.setblocking(False)
        except OSError as e:
            logging.error(
                f"UdpVideoProxy: failed to bind port {self.video_port}: {e}"
            )
            if self._external_sock:
                self._external_sock.close()
                self._external_sock = None
            return False

        self.local_port = self._find_free_local_port()
        if self.local_port == 0:
            logging.error("UdpVideoProxy: failed to find free local port")
            self._external_sock.close()
            self._external_sock = None
            return False

        self._forward_sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM
        )

        self.start()
        return True

    def stop(self) -> None:
        self._running.clear()

    def run(self) -> None:
        self._running.set()
        forward_addr = ("127.0.0.1", self.local_port)
        heartbeat_bytes = Heartbeat().to_bytes()
        last_heartbeat = 0.0

        logging.info(
            f"UdpVideoProxy: forwarding :{self.video_port} -> "
            f"localhost:{self.local_port}, heartbeats to {self.relay_address}"
        )

        # Send initial heartbeat immediately
        try:
            self._external_sock.sendto(heartbeat_bytes, self.relay_address)
            last_heartbeat = time.monotonic()
        except OSError as e:
            logging.warning(f"UdpVideoProxy: initial heartbeat failed: {e}")

        while self._running.is_set():
            try:
                readable, _, _ = select.select(
                    [self._external_sock], [], [], 1.0
                )
            except (OSError, ValueError):
                break

            if readable:
                try:
                    while True:
                        data, _ = self._external_sock.recvfrom(
                            RECV_BUFFER_SIZE
                        )
                        self._forward_sock.sendto(data, forward_addr)
                except BlockingIOError:
                    pass
                except OSError as e:
                    if self._running.is_set():
                        logging.warning(
                            f"UdpVideoProxy: forward error: {e}"
                        )

            now = time.monotonic()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL_S:
                try:
                    self._external_sock.sendto(
                        heartbeat_bytes, self.relay_address
                    )
                    last_heartbeat = now
                    logging.debug(
                        f"UdpVideoProxy: heartbeat sent to "
                        f"{self.relay_address}"
                    )
                except OSError as e:
                    logging.warning(
                        f"UdpVideoProxy: heartbeat failed: {e}"
                    )

        for sock in (self._external_sock, self._forward_sock):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

        logging.info("UdpVideoProxy: stopped")

    @staticmethod
    def _find_free_local_port() -> int:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()
            return port
        except OSError:
            return 0
