from concurrent.futures import ThreadPoolExecutor
import logging
import threading
import time
from typing import Dict, Callable, Optional
import socket

from v3xctrl_helper import Address

from .Base import Base
from .message import Message, Syn, Ack, Command, CommandAck
from .MessageHandler import MessageHandler
from .State import State
from .UDPTransmitter import UDPTransmitter


class Server(Base):
    MAX_WORKERS = 10
    COMMAND_DELAY = 0.2

    def __init__(self, port: int, ttl_ms: int = 100) -> None:
        super().__init__()

        self.port = port
        self.no_message_timeout = 10

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', self.port))
        self.socket.settimeout(1)

        self.transmitter = UDPTransmitter(self.socket, ttl_ms)
        self.message_handler = MessageHandler(self.socket)

        self.pending_commands: Dict[str, Callable[[bool], None] | None] = {}
        self.pending_lock = threading.Lock()

        self.thread_pool = ThreadPoolExecutor(
            max_workers=self.MAX_WORKERS,
            thread_name_prefix=f"Server-{port}"
        )

    def syn_handler(self, message: Syn, addr: Address) -> None:
        super()._send(Ack(), addr)
        if self.state == State.WAITING:
            self.handle_state_change(State.CONNECTED)

    def send(self, message: Message) -> None:
        addr = self.get_last_address()
        if addr:
            super()._send(message, addr)

    def command_ack_handler(
        self,
        message: CommandAck,
        addr: Address
    ) -> None:
        command_id = message.get_command_id()
        with self.pending_lock:
            callback = self.pending_commands.pop(command_id, None)
            if callback:
                callback(True)

    def send_command(
        self,
        command: Command,
        callback: Optional[Callable[[bool], None]] = None,
        max_retries: int = 10
    ) -> None:
        """Sends a command up to max_retries or until answer is received."""
        command_id = command.get_command_id()

        def retry_task() -> None:
            try:
                for attempt in range(max_retries):
                    with self.pending_lock:
                        if command_id not in self.pending_commands:
                            return

                    self.send(command)

                    # Do not sleep after last attempt
                    if attempt < max_retries - 1:
                        time.sleep(self.COMMAND_DELAY)

                # Timeout - no ACK received
                with self.pending_lock:
                    if command_id in self.pending_commands:
                        del self.pending_commands[command_id]
                        if callback:
                            callback(False)
            except Exception as e:
                logging.error(f"Error in command retry task: {e}")
                with self.pending_lock:
                    self.pending_commands.pop(command_id, None)
                if callback:
                    callback(False)

        with self.pending_lock:
            self.pending_commands[command_id] = callback

        try:
            self.thread_pool.submit(retry_task)
        except RuntimeError:
            # Thread pool is shut down, clean up and notify failure
            with self.pending_lock:
                self.pending_commands.pop(command_id, None)
            if callback:
                callback(False)

    def run(self) -> None:
        self.started.set()

        self.transmitter.start()
        self.transmitter.start_task()

        self.message_handler.start()

        # External handlers added via subscribe
        self.message_handler.add_handler(Message, self.all_handler)

        # Class specific Handlers
        self.message_handler.add_handler(Syn, self.syn_handler)
        self.message_handler.add_handler(CommandAck, self.command_ack_handler)

        self.running.set()
        while self.running.is_set():
            if self.state == State.DISCONNECTED:
                self.message_handler.reset()
                self.handle_state_change(State.WAITING)

            elif self.state == State.WAITING:
                pass

            elif self.state == State.SPECTATING:
                self.heartbeat()

            elif self.state == State.CONNECTED:
                self.check_timeout()
                self.heartbeat()

            time.sleep(self.STATE_CHECK_INTERVAL_MS / 1000)

    def stop(self) -> None:
        if self.started.is_set():
            # Wait for the setup to be done before tearing everything down
            self.running.wait()

            # Notify all pending commands about shutdown
            with self.pending_lock:
                for callback in self.pending_commands.values():
                    if callback:
                        callback(False)
                self.pending_commands.clear()

            self.started.clear()

            self.message_handler.stop()
            self.transmitter.stop()

            self.message_handler.join()
            self.transmitter.join()

            self.running.clear()

        self.thread_pool.shutdown(wait=False)
        self.socket.close()

    def update_ttl(self, ttl_ms: int) -> None:
        self.transmitter.update_ttl(ttl_ms)
