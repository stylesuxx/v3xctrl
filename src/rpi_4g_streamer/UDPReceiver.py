"""
Receive UDP packets and forward them to handler.

The receiver only forwards valid packets. For a packet to be considered
valid the following conditions must be met:
- The data must be of a Message subtype
- The timestamp must be higher than the last received timestamp
- Validate host (optional)
"""
import logging
import select
import socket
import threading
from typing import Callable, Tuple

from .Message import Message


class UDPReceiver(threading.Thread):
    TIMEOUT = 5
    BUFFERSIZE = 4096

    def __init__(self, sock: socket.socket, handler: Callable[[Message, Tuple[str, int]], None]):
        super().__init__(daemon=True)

        self.socket = sock
        self.handler = handler
        self.last_timestamp = 0

        self.should_validate_host = False
        self.valid_host = None

        self.running = threading.Event()
        self.running.clear()

    def set_socket(self, sock: socket.socket) -> None:
        self.socket = sock

    def is_valid_message(self, message: Message, addr: Tuple[str, int]) -> bool:
        if message.timestamp <= self.last_timestamp:
            return False

        if self.should_validate_host and addr[0] != self.valid_host:
            return False

        return True

    def run(self) -> None:
        self.running.set()
        while self.running.is_set():
            try:
                ready, _, _ = select.select([self.socket], [], [], self.TIMEOUT)
                if ready:
                    data, addr = self.socket.recvfrom(self.BUFFERSIZE)

                    if data:
                        try:
                            message = Message.from_bytes(data)
                            if self.is_valid_message(message, addr):
                                self.last_timestamp = message.timestamp
                                self.handler(message, addr)
                        except Exception as e:
                            logging.warning(f"Error while processing packet {addr}: {e}")
            except (socket.error, OSError) as e:
                logging.debug(f"Socket error: {e}")

    def validate_host(self, host: str):
        self.valid_host = host
        self.should_validate_host = True

    def stop(self) -> None:
        if self.running.is_set():
            self.running.clear()
