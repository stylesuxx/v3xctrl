"""
Receive UDP packets and forward them to handler.

The receiver only forwards valid packets. For a packet to be considered
valid the following conditions must be met:
- The data must be of a Message subtype
- The timestamp must be higher than the last received timestamp
- Validate host (optional)

NOTE: The kernel avoids buildup by dropping older UDP packets when new ones
      arrive faster than the application can process them. Since we are only
      interested in the most recent data, this behavior is beneficial and does
      not require special handling on our side.
"""
import logging
import queue
import select
import socket
import threading
from typing import Callable, Tuple, Optional

from .Message import Message


class UDPReceiver(threading.Thread):
    # Max possible datagram size
    BUFFERSIZE = 65535

    def __init__(self,
                 sock: socket.socket,
                 handler: Callable[[Message, Tuple[str, int]], None],
                 timeout: int = 0.1):
        super().__init__(daemon=True)

        self.socket = sock
        assert self.socket.type == socket.SOCK_DGRAM, "UDPReceiver expects a UDP socket"

        self.handler = handler
        self.timeout = timeout

        self.last_timestamp = 0

        self._should_validate_host = False
        self._expected_host: Optional[str] = None

        self._running = threading.Event()

        self._queue = queue.Queue(maxsize=100)
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)

    def is_valid_message(self, message: Message, addr: Tuple[str, int]) -> bool:
        if message.timestamp <= self.last_timestamp:
            logging.debug("Skipping out of order message")
            return False

        if self._should_validate_host and addr[0] != self._expected_host:
            logging.debug("Skipping message from wrong host")
            return False

        return True

    def run(self) -> None:
        self._running.set()
        self._worker_thread.start()
        try:
            while self._running.is_set():
                try:
                    ready, _, _ = select.select([self.socket], [], [], self.timeout)
                except (ValueError, socket.error, OSError) as e:
                    logging.error(f"Socket error during select: {e}")
                    break

                # Timeout, no data ready
                if not ready:
                    continue

                try:
                    data, addr = self.socket.recvfrom(self.BUFFERSIZE)
                except (socket.error, OSError) as e:
                    logging.error(f"Socket error during recvfrom: {e}")
                    break

                # No data received
                if not data:
                    continue

                try:
                    message = Message.from_bytes(data)
                except Exception as e:
                    logging.warning(f"Error while decoding packet from {addr}: {e}")
                    continue

                if self.is_valid_message(message, addr):
                    self.last_timestamp = message.timestamp
                    try:
                        self._queue.put_nowait((message, addr))
                    except queue.Full:
                        logging.warning("Handler queue full, dropping packet")

        finally:
            self._running.clear()

    def _worker_loop(self) -> None:
        while self.is_running():
            try:
                message, addr = self._queue.get(timeout=self.timeout)
                self.handler(message, addr)
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Error in handler: {e}")

    def validate_host(self, host_ip: str):
        self._expected_host = host_ip
        self._should_validate_host = True

    def is_running(self) -> bool:
        return self._running.is_set()

    def stop(self) -> None:
        if self._running.is_set():
            self._running.clear()
