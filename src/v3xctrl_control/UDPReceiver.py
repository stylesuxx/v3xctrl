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
import time
from typing import Callable, Tuple, Optional

from v3xctrl_helper import Address

from .message import (
  Message,
  PeerInfo,
  Syn,
  Ack,
  Command,
  CommandAck,
  Latency,
)


class UDPReceiver(threading.Thread):
    # Max possible datagram size
    BUFFERSIZE = 65535

    def __init__(
        self,
        sock: socket.socket,
        handler: Callable[[Message, Tuple[str, int]], None],
        timeout_ms: int = 100,
        window_ms: int = 500,
        should_validate_timestamp: bool = False,
    ):
        super().__init__(daemon=True)

        self.socket = sock
        assert self.socket.type == socket.SOCK_DGRAM, "UDPReceiver expects a UDP socket"

        self.handler = handler
        self.timeout = timeout_ms / 1000
        self.window = window_ms / 1000

        self.last_valid_timestamp = 0
        self.last_valid_now = None

        self._should_validate_timestamp = should_validate_timestamp
        self._should_validate_host = False
        self._expected_host: Optional[str] = None

        self._running = threading.Event()

        self._queue: queue.Queue[Tuple[Message, Address]] = queue.Queue(maxsize=100)
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)

    def is_valid_message(self, message: Message, addr: Tuple[str, int]) -> bool:
        if isinstance(message, PeerInfo):
            logging.debug("Skipping PeerInfo - already set up")
            return False

        if self._should_validate_host and addr[0] != self._expected_host:
            logging.warning(f"Skipping message from wrong host: {addr[0]}")
            return False

        # By default all Messages are order critical, we exempt this ones since
        # order does not matter, we need them processed in any case
        if (
            isinstance(message, Command) or
            isinstance(message, CommandAck) or
            isinstance(message, Latency)
        ):
            return True

        # Reset timestamps on Syn or Ack
        if isinstance(message, Syn) or isinstance(message, Ack):
            logging.debug("Resetting timestamps...")
            self.reset()
            return True

        """
        Check timestamps for every packet where we are only interested in the
        newest version. This is a catchall, but will effectively catch:
        - Telemetry
        - Control
        """
        if message.timestamp < self.last_valid_timestamp:
            logging.debug(f"Skipping out of order message: {message.type}")
            return False

        """
        When there has been a break up, we might receive messages that have
        been queued up, but are practically invalid at this point. We drop those
        messages and assume there will be new, more up to date messages soon.
        """
        if self.last_valid_now is not None and self._should_validate_timestamp:
            delta = time.time() - self.last_valid_now
            min_timestamp = self.last_valid_timestamp + delta - self.window
            if message.timestamp < min_timestamp:
                logging.debug("Skipping message: Timestamp too old")
                return False

        return True

    def reset(self) -> None:
        self.last_valid_timestamp = 0
        self.last_valid_now = None

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
                    self.last_valid_timestamp = message.timestamp
                    self.last_valid_now = time.time()
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

    def validate_host(self, host_ip: str) -> None:
        self._expected_host = host_ip
        self._should_validate_host = True

    def is_running(self) -> bool:
        return self._running.is_set()

    def stop(self) -> None:
        if self._running.is_set():
            self._running.clear()
