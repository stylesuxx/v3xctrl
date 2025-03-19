"""
Receive UDP packets and forward them to handler.

The receiver only forwards valid packages. For a package to be considered
valid the following conditions must be met:
- The data must be of a Message subtype
- The timestamp must be higher than the last received timestamp
"""
import threading
import socket
from typing import Callable, Tuple
import select

from .Message import Message


TIMEOUT = 5
BUFFERSIZE = 4096


class UDPReceiver(threading.Thread):
    def __init__(self, port: int, handler: Callable[[Message, Tuple[str, int]], None]):
        super().__init__(daemon=True)

        self.port = port
        self.handler = handler
        self.last_timestamp = 0

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", port))

        self.running = threading.Event()
        self.running.clear()

    def run(self) -> None:
        self.running.set()
        while self.running.is_set():
            try:
                ready, _, _ = select.select([self.sock], [], [], TIMEOUT)
                if ready:
                    data, addr = self.sock.recvfrom(BUFFERSIZE)

                    if data:
                        try:
                            message = Message.from_bytes(data)
                            if message.timestamp > self.last_timestamp:
                                self.last_timestamp = message.timestamp
                                self.handler(message, addr)
                        except Exception as e:
                            print(f"Invalid data received from {addr}: {e}")
            except (socket.error, ValueError, OSError) as e:
                pass  # Ignore select error (eg.: Timeout)

    def stop(self) -> None:
        if self.running.is_set():
            self.running.clear()
            self.sock.close()
