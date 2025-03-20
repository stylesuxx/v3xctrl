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
from typing import Tuple
import time
import logging
import socket

from .UDPTransmitter import UDPTransmitter
from .MessageHandler import MessageHandler
from .Message import Message, Syn, Ack, Heartbeat, Telemetry, Control
from .State import State
from .Base import Base

logging.basicConfig(level=logging.DEBUG)


class Client(Base):
    def __init__(self, host, port):
        super().__init__()

        self.host = host
        self.port = port

        # Re-use the same socket that we use for sending, for listening
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(1)

        # Setup message handler with host validation and custom socket
        self.transmitter = UDPTransmitter(self.socket)
        self.message_handler = MessageHandler(self.socket, host)

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
        self.last_message_timestamp = time.time()

    def syn_handler(self, message: Syn, addr: Tuple[str, int]) -> None:
        self.send(Ack())

    def ack_handler(self, message: Ack, addr: Tuple[str, int]) -> None:
        self.state = State.CONNECTED
        print("Got Ack")

    def heartbeat_handler(self, message: Heartbeat, addr: Tuple[str, int]) -> None:
        pass

    def control_handler(self, message: Control, addr: Tuple[str, int]) -> None:
        logging.debug(f"Received control message: {message}")

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
        # self.message_handler.add_handler(Syn, self.syn_handler)
        self.message_handler.add_handler(Ack, self.ack_handler)
        # self.message_handler.add_handler(Heartbeat, self.heartbeat_handler)
        self.message_handler.add_handler(Control, self.control_handler)

        self.running.set()
        while self.running.is_set():
            if self.state == State.DISCONNECTED:
                break

            if self.state == State.WAITING:
                self.send(Control({
                    "ste": 50,
                    "thr": 0
                }))
                time.sleep(self.interval["syn"])
            else:
                self.check_timeout()

            if self.state == State.CONNECTED:
                self.update_telemetry()
                self.check_connection()
                time.sleep(self.interval["telemetry"])

        self.stop()

    def stop(self):
        if self.started.is_set():
            self.started.clear()

            self.running.wait()

            self.message_handler.stop()
            self.transmitter.stop()

            self.message_handler.join()
            self.transmitter.join()

            self.running.clear()
