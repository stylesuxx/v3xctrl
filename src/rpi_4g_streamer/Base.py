"""
Base class for Server AND Client - disregard the name, they share more
than you might think.
"""
import threading
import logging
from typing import Tuple
import time

from .State import State
from .UDPTransmitter import UDPTransmitter
from .Message import Message


class Base(threading.Thread):
    def __init__(self):
        super().__init__()

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
        self.last_message_timestamp = None
        self.no_message_timeout = 5

    def handle_state_change(self, new_state: State) -> None:
        logging.debug(f"State changed from '{self.state}' to '{new_state}'")
        self.state = new_state

    def send(self, message: Message, addr: Tuple[str, int]) -> None:
        self.transmitter.add_message(message, addr)

    def get_last_address(self) -> Tuple[str, int]:
        return self.message_history[-1][1]

    def check_timeout(self):
        if self.state != State.DISCONNECTED:
            now = time.time()
            if now > self.last_message_timestamp + self.no_message_timeout:
                self.handle_state_change(State.DISCONNECTED)
