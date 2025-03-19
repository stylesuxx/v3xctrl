"""
The client can be in one of three states and only progress through them
sequentially:

1. WAITING: The client is sending SYN messages to the server and waiting for an
  ACK.
2. CONNECTED: The client has established an initial connection with the server.
  In this state the client is sending telemetry to the server in fixed
  intervals.
3. DISCONNECTED: For some reason the connection has been deemed disconnected.
  Either the client is no longer reaching the server or has not received
  messages from the server for a certain amount of time.
"""
import threading
from typing import Tuple
from enum import Enum
import time

from .MessageHandler import MessageHandler
from .Message import Message, Syn, Ack, Heartbeat, Telemetry, Command
from .UDPTransmitter import UDPTransmitter


class State(Enum):
    WAITING = "waiting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class Client(threading.Thread):
    def __init__(self, host, port):
        super().__init__(daemon=True)

        self.host = host
        self.port = port

        self.message_history = []
        self.message_history_length = 50

        self.running = threading.Event()
        self.running.clear()

        self.started = threading.Event()
        self.started.clear()

        # Setup message handler with host validation
        self.message_handler = MessageHandler(self.port, host)
        self.transmitter = UDPTransmitter()

        self.state = State.WAITING

        self.interval = {
            "syn": 1,
            "telemetry": 1,
        }

    def all_handler(self, message: Message, addr: Tuple[str, int]) -> None:
        """
        Generic message handler, should be called from each handler.
        Is responsible for some general housekeeping:
        - build and maintain message history
        """
        self.message_history.append((message, addr))
        self.message_history = self.message_history[-self.message_history_length:]

    def syn_handler(self, message: Syn, addr: Tuple[str, int]) -> None:
        self.send(Ack())

    def ack_handler(self, message: Ack, addr: Tuple[str, int]) -> None:
        self.state = State.CONNECTED

    def heartbeat_handler(self, message: Heartbeat, addr: Tuple[str, int]) -> None:
        pass

    def command_handler(self, message: Command, addr: Tuple[str, int]) -> None:
        # Handle incoming commands by controling the actualtors
        pass

    def get_last_address(self) -> Tuple[str, int]:
        if self.message_history:
            return self.message_history[-1][1]

    def send(self, message: Message) -> None:
        """ Messages are always sent to the configured host and port. """
        self.transmitter.add_message(message, (self.host, self.port))

    def update_telemetry(self):
        telemetry = Telemetry({
            "key_1": "value_1"
        })
        self.send(telemetry)

    def check_connection(self):
        # Make sure that we are still connected to the server
        # self.state = State.DISCONNECTED
        pass

    def run(self):
        self.started.set()

        self.transmitter.start()
        self.transmitter.start_task()

        self.message_handler.start()

        self.message_handler.add_handler(Message, self.all_handler)
        self.message_handler.add_handler(Syn, self.syn_handler)
        self.message_handler.add_handler(Ack, self.ack_handler)
        self.message_handler.add_handler(Heartbeat, self.heartbeat_handler)

        self.running.set()
        while self.running.is_set():
            if self.state == State.WAITING:
                self.send(Syn())
                time.sleep(self.interval["syn"])

            if self.state == State.CONNECTED:
                self.update_telemetry()
                self.check_connection()
                time.sleep(self.interval["telemetry"])

            if self.state == State.DISCONNECTED:
                self.stop()

        self.message_handler.join()
        self.transmitter.join()

    def stop(self):
        if self.started.is_set():
            self.started.clear()

            self.running.wait()

            self.message_handler.stop()
            self.transmitter.stop()

            self.running.clear()
