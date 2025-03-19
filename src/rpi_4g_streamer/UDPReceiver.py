"""
Receive UDP packets and forward them to handler.

The receiver only forwards valid packets. For a packet to be considered
valid the following conditions must be met:
- The data must be of a Message subtype
- The timestamp must be higher than the last received timestamp
- Validate host (optional)
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

        self.should_validate_host = False
        self.valid_host = None

        self.sock = None
        if self.port:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(("0.0.0.0", port))

        self.running = threading.Event()
        self.running.clear()

    def set_socket(self, sock: socket.socket) -> None:
        self.sock = sock

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
                                if self.should_validate_host:
                                    if addr[0] != self.valid_host:
                                        raise ValueError("Invalid host.")

                                self.last_timestamp = message.timestamp
                                self.handler(message, addr)
                        except Exception as e:
                            print(f"Error while processing packet {addr}: {e}")
            except (socket.error, ValueError, OSError) as e:
                pass  # Ignore select error (eg.: Timeout)

    def validate_host(self, host: str):
        self.valid_host = host
        self.should_validate_host = True

    def stop(self) -> None:
        if self.running.is_set():
            self.running.clear()
            self.sock.close()
