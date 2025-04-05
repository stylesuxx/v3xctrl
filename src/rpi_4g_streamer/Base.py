"""
Base class for Server AND Client - disregard the name, they share more
than you might think.
"""
import threading
import logging
from typing import Tuple, Callable
import time

from .State import State
from .Message import Message


class Base(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)

        self.state_handlers = []
        self.subscriptions = []
        self.message_history = []
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

    def subscribe(self, cls: type, handler: Callable[[Message], None]):
        """ Subscribe to messages. """
        self.subscriptions.append({
            "type": cls,
            "func": handler
        })

    def on(self, state: State, handler: Callable[[None], None]):
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

    def send(self, message: Message, addr: Tuple[str, int]) -> None:
        if self.transmitter:
            self.transmitter.add_message(message, addr)
            self.last_sent_timestamp = time.time()

    def get_last_address(self) -> Tuple[str, int]:
        if len(self.message_history) > 0:
            return self.message_history[-1][1]

        return None

    def check_timeout(self):
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
