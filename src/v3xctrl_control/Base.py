"""
Base class for Server AND Client - disregard the name, they share more
than you might think.
"""
from abc import ABC, abstractmethod
import threading
import logging
from typing import Tuple, Callable, List
import time

from v3xctrl_helper import Address, MessageHandler, StateHandler

from .State import State
from .Message import Message, Heartbeat


class Base(threading.Thread, ABC):
    STATE_CHECK_INTERVAL_MS = 1000

    def __init__(self) -> None:
        super().__init__(daemon=True)

        self.state_handlers: List[StateHandler] = []
        self.subscriptions: List[MessageHandler] = []
        self.message_history: List[Tuple[Message, Address]] = []
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

    def subscribe(self, cls: type, handler: Callable[[Message], None]) -> None:
        """ Subscribe to messages. """
        self.subscriptions.append({
            "type": cls,
            "func": handler
        })

    def on(self, state: State, handler: Callable[[], None]) -> None:
        """ Subscribe to state changes. """
        self.state_handlers.append({
            "state": state,
            "func": handler
        })

    def handle_state_change(self, new_state: State) -> None:
        logging.debug(f"State changed from '{self.state}' to '{new_state}'")
        self.state = new_state

        for handler in self.state_handlers:
            if handler['state'] == new_state:
                handler['func']()

    @abstractmethod
    def send(self, message: Message) -> None:
        pass

    def heartbeat(self) -> None:
        """
        If nothing has been sent in a while, send a hearbeat to keep the client
        open.
        """
        now = time.time()
        if now - self.last_sent_timestamp > self.last_sent_timeout:
            self.send(Heartbeat())

    def _send(self, message: Message, addr: Tuple[str, int]) -> None:
        if self.transmitter:
            self.transmitter.add_message(message, addr)
            self.last_sent_timestamp = time.time()

    def get_last_address(self) -> Tuple[str, int] | None:
        if len(self.message_history) > 0:
            return self.message_history[-1][1]

        return None

    def check_timeout(self) -> None:
        if self.state != State.DISCONNECTED:
            now = time.time()
            if now > self.last_message_timestamp + self.no_message_timeout:
                self.handle_state_change(State.DISCONNECTED)

    def all_handler(self, message: Message, addr: Tuple[str, int]) -> None:
        """
        All messages are handled here.
        Registered (external) handlers will get messages forwarded from here
        """
        self.message_history.append((message, addr))
        self.message_history = self.message_history[-self.message_history_length:]
        self.last_message_timestamp = time.time()

        for subscription in self.subscriptions:
            if subscription['type'] == type(message):
                subscription['func'](message)
