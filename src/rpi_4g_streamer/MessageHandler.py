"""
MessageHandler handles incoming UDP messages and forwards them to registered
handlers.

Every message type can have mutliple handlers and the message is forwarded to
all of them. Message handlers are triggered in the order they are registered.
"""

import threading
from typing import Callable, Tuple

from .UDPReceiver import UDPReceiver
from .Message import Message


class MessageHandler(threading.Thread):
    def __init__(self, port: int, valid_host: str = None):
        super().__init__(daemon=True)

        self.port = port
        self.handlers = []

        self.rx = UDPReceiver(self.port, self.handler)
        if valid_host:
            self.rx.validate_host(valid_host)

        self.started = threading.Event()
        self.started.clear()

        self.running = threading.Event()
        self.running.clear()

    def handler(self, message: Message, addr: Tuple[str, int]) -> None:
        for h in self.handlers:
            if isinstance(message, h['type']):
                h['handler'](message, addr)

    def add_handler(self, cls: type, handler: Callable[[Message, Tuple[str, int]], None]) -> None:
        self.handlers.append({
            "type": cls,
            "handler": handler
        })

    def run(self) -> None:
        self.started.set()

        self.rx.start()
        self.running.set()

        self.rx.join()

    def stop(self) -> None:
        if self.started.is_set():
            self.running.wait()
            self.rx.stop()
            self.running.clear()
            self.started.clear()
