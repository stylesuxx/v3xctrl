from typing import Tuple
import threading
import time
import socket

from .Base import Base
from .Message import Message, Syn, Ack, Command, CommandAck
from .MessageHandler import MessageHandler
from .State import State
from .UDPTransmitter import UDPTransmitter


class Server(Base):
    COMMAND_MAX_RETRIES = 10
    COMMAND_DELAY = 1

    def __init__(self, port):
        super().__init__()

        self.port = port
        self.no_message_timeout = 10

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', self.port))
        self.socket.settimeout(1)

        self.transmitter = UDPTransmitter(self.socket)
        self.message_handler = MessageHandler(self.socket)

        self.pending_commands = {}
        self.pending_lock = threading.Lock()

    def syn_handler(self, message: Syn, addr: Tuple[str, int]) -> None:
        super()._send(Ack(), addr)
        if self.state == State.WAITING:
            self.handle_state_change(State.CONNECTED)

    def command_ack_handler(self, message: CommandAck, addr: Tuple[str, int]) -> None:
        command_id = message.get_command_id()
        with self.pending_lock:
            callback = self.pending_commands.pop(command_id, None)
            if callback:
                callback(True)

    def send(self, message: Message) -> None:
        addr = self.get_last_address()
        if addr:
            super()._send(message, addr)

    def send_command(self, command: Command, callback: callable = None) -> None:
        """Attempts to send a command up to 10 times before failing."""
        command_id = command.get_command_id()

        def retry_task():
            for attempt in range(self.COMMAND_MAX_RETRIES):
                with self.pending_lock:
                    if command_id not in self.pending_commands:
                        return

                self.send(command)
                time.sleep(self.COMMAND_DELAY)

            # If no Ack received yet, we fail
            with self.pending_lock:
                if command_id in self.pending_commands:
                    del self.pending_commands[command_id]
                    if callback:
                        callback(False)

        with self.pending_lock:
            self.pending_commands[command_id] = callback

        threading.Thread(target=retry_task, daemon=True).start()

    def run(self):
        self.started.set()

        self.transmitter.start()
        self.transmitter.start_task()

        self.message_handler.start()
        self.message_handler.add_handler(Message, self.all_handler)
        self.message_handler.add_handler(Syn, self.syn_handler)
        self.message_handler.add_handler(CommandAck, self.command_ack_handler)

        self.running.set()
        while self.running.is_set():
            if self.state == State.DISCONNECTED:
                self.handle_state_change(State.WAITING)

            elif self.state == State.WAITING:
                pass

            elif self.state == State.CONNECTED:
                self.check_timeout()
                self.heartbeat()

            time.sleep(self.STATE_CHECK_INTERVAL_MS / 1000)

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
