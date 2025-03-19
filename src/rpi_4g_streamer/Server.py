import threading
from typing import Tuple
from enum import Enum
import time

from .MessageHandler import MessageHandler
from .UDPTransmitter import UDPTransmitter
from .Message import Message, Syn, Ack, Telemetry, Control


class State(Enum):
    WAITING = "waiting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class Server(threading.Thread):
    def __init__(self, port):
        super().__init__(daemon=True)

        self.port = port

        self.message_history = []
        self.message_history_length = 50

        self.running = threading.Event()
        self.running.clear()

        self.started = threading.Event()
        self.started.clear()

        self.message_handler = MessageHandler(self.port)
        self.transmitter = UDPTransmitter()

        self.state = State.WAITING

    def all_handler(self, message: Message, addr: Tuple[str, int]) -> None:
        """
        Generic message handler, should be called from each handler.
        Is responsible for some general housekeeping:
        - build and maintain message history
        """
        self.message_history.append((message, addr))
        self.message_history = self.message_history[-self.message_history_length:]

    def syn_handler(self, message: Syn, addr: Tuple[str, int]) -> None:
        self.send(Ack(), addr)
        self.state = State.CONNECTED

    def telemetry_handler(self, message: Telemetry, addr: Tuple[str, int]) -> None:
        print(message)

    def send(self, message: Message, addr: Tuple[str, int]) -> None:
        self.transmitter.add_message(message, addr)

    def get_last_address(self) -> Tuple[str, int]:
        return self.message_history[-1][1]

    def update_controlls(self):
        control = Control({
            "ctrl_1": "val_1"
        })

        addr = self.get_last_address()
        self.send(control, addr)

    def run(self):
        self.started.set()

        self.transmitter.start()
        self.transmitter.start_task()

        self.message_handler.start()
        self.message_handler.add_handler(Message, self.all_handler)
        self.message_handler.add_handler(Syn, self.syn_handler)
        self.message_handler.add_handler(Telemetry, self.telemetry_handler)

        self.running.set()
        while self.running.is_set():
            if self.state == State.WAITING:
                """ Wait for client to connect. """
                print("Waiting for client...")
                time.sleep(1)
            if self.state == State.CONNECTED:
                self.update_controlls()
                time.sleep(1)

        self.message_handler.join()
        self.transmitter.join()

    def stop(self):
        if self.started.is_set():
            self.started.clear()

            self.running.wait()

            self.message_handler.stop()
            self.transmitter.stop()

            self.running.clear()
