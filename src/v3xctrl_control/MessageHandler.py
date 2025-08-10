"""
MessageHandler handles incoming UDP messages and forwards them to registered
handlers.

Every message type can have mutliple handlers and the message is forwarded to
all of them. Message handlers are triggered in the order they are registered.
"""

from __future__ import annotations
from collections import defaultdict
import socket
import threading
from typing import (
  Dict,
  List,
  Optional,
  Protocol,
  TypeVar,
  Any,
)

from v3xctrl_helper import Address

from .UDPReceiver import UDPReceiver
from .Message import Message

T = TypeVar("T", bound=Message, contravariant=True)


class Handler(Protocol[T]):
    def __call__(self, msg: T, addr: Address, /) -> None: ...


class MessageHandler(threading.Thread):
    def __init__(
        self,
        sock: socket.socket,
        valid_host_ip: Optional[str] = None
    ) -> None:
        super().__init__(daemon=True)

        self.socket = sock
        self.handlers: Dict[type[Message], List[Handler[Any]]] = defaultdict(list)

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
