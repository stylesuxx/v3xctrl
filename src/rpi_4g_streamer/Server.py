from typing import Tuple
import time
import socket

from .Base import Base
from .Message import Message, Syn, Ack, Heartbeat
from .MessageHandler import MessageHandler
from .State import State
from .UDPTransmitter import UDPTransmitter


class Server(Base):
    def __init__(self, port):
        super().__init__()

        self.port = port
        self.no_message_timeout = 10

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', self.port))
        self.socket.settimeout(1)

        self.transmitter = UDPTransmitter(self.socket)
        self.message_handler = MessageHandler(self.socket)

    def syn_handler(self, message: Syn, addr: Tuple[str, int]) -> None:
        super().send(Ack(), addr)
        if self.state == State.WAITING:
            self.handle_state_change(State.CONNECTED)

    def send(self, message: Message) -> None:
        addr = self.get_last_address()
        if addr:
            super().send(message, addr)

    def check_heartbeat(self):
        """
        If nothing has been sent in a while, send a hearbeat to keep the client
        open.
        """
        now = time.time()
        if now - self.last_sent_timestamp > self.last_sent_timeout:
            self.send(Heartbeat())

    def run(self):
        self.started.set()

        self.transmitter.start()
        self.transmitter.start_task()

        self.message_handler.start()
        self.message_handler.add_handler(Message, self.all_handler)
        self.message_handler.add_handler(Syn, self.syn_handler)

        self.running.set()
        while self.running.is_set():
            if self.state == State.DISCONNECTED:
                self.handle_state_change(State.WAITING)

            if self.state == State.WAITING:
                time.sleep(1)
            else:
                self.check_timeout()

            if self.state == State.CONNECTED:
                self.check_heartbeat()

            time.sleep(0.001)

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

        self.socket.close()
