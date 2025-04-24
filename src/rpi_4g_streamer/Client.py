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
import socket
import time
from typing import Tuple

from .Base import Base
from .Message import Message, Syn, Ack, Heartbeat
from .MessageHandler import MessageHandler
from .State import State
from .UDPTransmitter import UDPTransmitter


class Client(Base):
    def __init__(self, host, port):
        super().__init__()

        self.host = host
        self.port = port
        self.server_address = (self.host, self.port)

        self.interval = {
            "syn": 1,
        }

        # Consider client disconnected if it has not seen a packet from the
        # server for 3 seconds
        self.no_message_timeout = 3

    def syn_handler(self, message: Syn, addr: Tuple[str, int]) -> None:
        self.send(Ack())

    def ack_handler(self, message: Ack, addr: Tuple[str, int]) -> None:
        if self.state == State.WAITING:
            self.handle_state_change(State.CONNECTED)

    def send(self, message: Message) -> None:
        """ Messages are always sent to the server. """
        super().send(message, self.server_address)

    def check_heartbeat(self):
        """
        If nothing has been sent in a while, send a hearbeat to keep the hole
        open.
        """
        now = time.time()
        if now - self.last_sent_timestamp > self.last_sent_timeout:
            self.send(Heartbeat())

    def initialize(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(1)

        self.transmitter = UDPTransmitter(self.socket)
        self.message_handler = MessageHandler(self.socket, self.host)

        self.transmitter.start()
        self.transmitter.start_task()

        self.message_handler.start()
        self.message_handler.add_handler(Message, self.all_handler)
        self.message_handler.add_handler(Syn, self.syn_handler)
        self.message_handler.add_handler(Ack, self.ack_handler)

    def re_initialize(self):
        """ Cleanly tear down the current connection and build a new one."""
        if self.running.is_set():
            self.message_handler.stop()
            self.transmitter.stop()

            self.message_handler.join()
            self.transmitter.join()

            self.socket.close()

        self.initialize()

    def run(self):
        self.started.set()

        self.initialize()

        self.running.set()
        while self.running.is_set():
            if self.state == State.DISCONNECTED:
                self.re_initialize()
                self.handle_state_change(State.WAITING)

            if self.state == State.WAITING:
                self.send(Syn())
                time.sleep(self.interval["syn"])
            else:
                self.check_timeout()

            if self.state == State.CONNECTED:
                self.check_heartbeat()

            time.sleep(0.02)

    def stop(self):
        if self.started.is_set():
            self.started.clear()

            self.running.wait()

            self.message_handler.stop()
            self.transmitter.stop()

            self.message_handler.join()
            self.transmitter.join()

            self.running.clear()

            self.socket.close()
