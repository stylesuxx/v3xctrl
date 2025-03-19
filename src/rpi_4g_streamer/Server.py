import logging
from typing import Tuple
import time

from .MessageHandler import MessageHandler
from .Message import Message, Syn, Ack, Telemetry, Control
from .State import State
from .Base import Base

logging.basicConfig(level=logging.DEBUG)


class Server(Base):
    def __init__(self, port):
        super().__init__()

        self.port = port
        self.no_message_timeout = 10
        self.message_handler = MessageHandler(self.port)

    def all_handler(self, message: Message, addr: Tuple[str, int]) -> None:
        """
        Generic message handler, should be called from each handler.
        Is responsible for some general housekeeping:
        - build and maintain message history
        """
        self.message_history.append((message, addr))
        self.message_history = self.message_history[-self.message_history_length:]
        self.last_message_timestamp = time.time()

    def syn_handler(self, message: Syn, addr: Tuple[str, int]) -> None:
        self.send(Ack(), addr)
        self.handle_state_change(State.CONNECTED)

    def telemetry_handler(self, message: Telemetry, addr: Tuple[str, int]) -> None:
        logging.debug(f"Received telemetry message: {message}")

    def update_controls(self):
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
            if self.state == State.DISCONNECTED:
                break

            if self.state == State.WAITING:
                time.sleep(1)
            else:
                self.check_timeout()

            if self.state == State.CONNECTED:
                self.update_controls()
                time.sleep(1)

        self.stop()

    def stop(self):
        if self.started.is_set():
            self.started.clear()

            # Wait for the setup to be done before tearing everything down
            self.running.wait()

            self.message_handler.stop()
            self.transmitter.stop()

            self.message_handler.join()
            self.transmitter.join()

            self.running.clear()
