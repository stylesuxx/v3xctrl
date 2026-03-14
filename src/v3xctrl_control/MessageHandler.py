"""
MessageHandler handles incoming UDP messages and forwards them to registered
handlers.

Every message type can have mutliple handlers and the message is forwarded to
all of them. Message handlers are triggered in the order they are registered.
"""

import socket
import threading
from collections import defaultdict
from typing import Any

from v3xctrl_helper import Address

from .handler_types import Handler, T
from .message import Message
from .UDPReceiver import UDPReceiver


class MessageHandler(threading.Thread):
    def __init__(
        self,
        sock: socket.socket,
        valid_host_ip: str | None = None
    ) -> None:
        super().__init__(daemon=True)

        self.socket = sock
        self.handlers: dict[type[Message], list[Handler[Any]]] = defaultdict(list)

        self.rx = UDPReceiver(self.socket, self.handler)
        if valid_host_ip:
            self.rx.validate_host(valid_host_ip)

        self.started = threading.Event()
        self.started.clear()

        self.running = threading.Event()
        self.running.clear()

    def handler(self, message: Message, addr: Address) -> None:
        for cls, handlers in self.handlers.items():
            if isinstance(message, cls):
                for fn in handlers:
                    fn(message, addr)

    def add_handler(self, cls: type[T], handler: Handler[T]) -> None:
        self.handlers[cls].append(handler)

    def reset(self) -> None:
        self.rx.reset()

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
