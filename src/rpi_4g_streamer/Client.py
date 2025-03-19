import threading
from typing import Tuple

from .MessageHandler import MessageHandler
from .Message import Message, Syn, Ack, Heartbeat
from .UDPTransmitter import UDPTransmitter


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

        self.message_handler = MessageHandler(self.port)
        self.transmitter = UDPTransmitter()

    def all_handler(self, message: Message, addr: Tuple[str, int]) -> None:
        """
        Generic message handler, should be called from each handler.
        Is responsible for some general housekeeping:
        - build message history
        """
        print(f'Got Message from {addr}')
        self.message_history.append((message, addr))
        self.message_history = self.message_history[-self.message_history_length:]

    def syn_handler(self, message: Syn, addr: Tuple[str, int]) -> None:
        print(f'Got Ack from {addr}')

    def ack_handler(self, message: Ack, addr: Tuple[str, int]) -> None:
        print(f'Got Ack from {addr}')

    def heartbeat_handler(self, message: Heartbeat, addr: Tuple[str, int]) -> None:
        print(f'Got Heartbeat from {addr}')

    def get_last_address(self) -> Tuple[str, int]:
        if self.message_history:
            return self.message_history[-1][1]

    def reply(self, message: Message) -> None:
        address = self.get_last_address()

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

        self.message_handler.join()
        self.transmitter.join()

    def stop(self):
        if self.started.is_set():
            self.running.wait()

            self.message_handler.stop()
            self.transmitter.stop()

            self.started.clear()
            self.running.clear()
