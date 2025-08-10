"""
Base class for Server AND Client - disregard the name, they share more
than you might think.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from collections import defaultdict
import threading
import logging
from typing import Callable, Dict, List, Protocol, TypeVar, Any
import time

from v3xctrl_helper import (
  Address,
  MessageFromAddress,
)

from .State import State
from .Message import Message, Heartbeat

T = TypeVar("T", bound=Message, contravariant=True)


class MessageHandler(Protocol[T]):
    def __call__(self, msg: T, /) -> None: ...


class Base(threading.Thread, ABC):
    STATE_CHECK_INTERVAL_MS = 1000

    def __init__(self) -> None:
        super().__init__(daemon=True)

        self.state_handlers: Dict[State, List[Callable[[], None]]] = defaultdict(list)
        self.subscriptions: Dict[type[Message], List[MessageHandler[Any]]] = defaultdict(list)
        self.message_history: List[MessageFromAddress] = []
        self.message_history_length = 50

        self.running = threading.Event()
        self.running.clear()

        self.started = threading.Event()
        self.started.clear()

        self.state = State.WAITING

        # Initalization needs to be done in the implementing class
        self.socket = None
        self.transmitter = None
        self.message_handler = None

        # The server timeout should be longer than on the client. This way
        # it is possible to recover a lost connection
        self.last_message_timestamp = 0
        self.no_message_timeout = 5

        self.last_sent_timestamp = 0
        self.last_sent_timeout = 1

    @abstractmethod
    def send(self, message: Message) -> None:
        pass

    def _send(self, message: Message, addr: Address) -> None:
        if self.transmitter:
            self.transmitter.add_message(message, addr)
            self.last_sent_timestamp = time.time()

    def heartbeat(self) -> None:
        """
        If nothing has been sent in a while, send a hearbeat to keep the client
        open.
        """
        now = time.time()
        if now - self.last_sent_timestamp > self.last_sent_timeout:
            self.send(Heartbeat())

    def get_last_address(self) -> Address | None:
        if len(self.message_history) > 0:
            return self.message_history[-1][1]

        return None

    def check_timeout(self) -> None:
        if self.state != State.DISCONNECTED:
            now = time.time()
            if now > self.last_message_timestamp + self.no_message_timeout:
                self.handle_state_change(State.DISCONNECTED)

    def subscribe(self, cls: type[T], handler: MessageHandler[T]) -> None:
        self.subscriptions[cls].append(handler)

    def on(self, state: State, handler: Callable[[], None]) -> None:
        self.state_handlers[state].append(handler)

    def handle_state_change(self, new_state: State) -> None:
        logging.debug(f"State changed from '{self.state}' to '{new_state}'")
        self.state = new_state

        for current_state, handlers in self.state_handlers.items():
            if current_state == new_state:
                for fn in handlers:
                    fn()

    def all_handler(self, message: Message, addr: Address) -> None:
        """
        All messages are handled here.
        Registered (external) handlers will get messages forwarded from here
        """
        self.message_history.append(MessageFromAddress(message, addr))
        self.message_history = self.message_history[-self.message_history_length:]
        self.last_message_timestamp = time.time()

        for cls, handlers in self.subscriptions.items():
            if isinstance(message, cls):
                for fn in handlers:
                    fn(message)
