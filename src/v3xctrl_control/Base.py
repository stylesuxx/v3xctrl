"""
Base class for Server AND Client - disregard the name, they share more
than you might think.
"""

import logging
import socket
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from v3xctrl_helper import (
    Address,
    MessageFromAddress,
)

from .handler_types import Handler, T
from .message import Heartbeat, Message
from .State import State

if TYPE_CHECKING:
    from .MessageHandler import MessageHandler
    from .UDPTransmitter import UDPTransmitter

logger = logging.getLogger(__name__)


class InitializationError(Exception):
    """Raised when a subclass is not properly initialized"""

    pass


class Base(threading.Thread, ABC):
    # Longest the run loop sleeps between two looks at its deadlines
    MAXIMUM_WAIT_SECONDS = 1.0

    def __init__(self) -> None:
        super().__init__(daemon=True)

        # Set by stop() so a waiting run loop ends at once
        self._wake = threading.Event()

        self.state_handlers: dict[State, list[Callable[[], None]]] = defaultdict(list)
        self.subscriptions: dict[type[Message], list[Handler[Any]]] = defaultdict(list)
        self.message_history: list[MessageFromAddress] = []
        self.message_history_length = 50

        self.running = threading.Event()
        self.running.clear()

        self.started = threading.Event()
        self.started.clear()

        self.state = State.WAITING

        # Silence beyond the message timeout engages the failsafe, silence
        # beyond the disconnect timeout tears the session down. Equal values
        # skip the failsafe and disconnect at once.
        self.last_message_timestamp: float = 0
        self.no_message_timeout: float = 5
        self.disconnect_timeout: float = 5
        # Stamp of the last message before the failsafe engaged; the resume
        # reports the silence from there, however many messages the receive
        # thread got in while the failsafe was engaging.
        self.silence_started_at: float = 0

        self.last_sent_timestamp: float = 0
        self.last_sent_timeout: float = 1

        self.socket: socket.socket | None = None
        self.transmitter: UDPTransmitter | None = None
        self.message_handler: MessageHandler | None = None

    def validate_initialization(self) -> None:
        """Validate that all required components are properly initialized."""
        missing: list[str] = []

        if not hasattr(self, "socket") or self.socket is None:
            missing.append("socket")

        if not hasattr(self, "transmitter") or self.transmitter is None:
            missing.append("transmitter")

        if not hasattr(self, "message_handler") or self.message_handler is None:
            missing.append("message_handler")

        if missing:
            raise InitializationError(f"Required components not initialized: {', '.join(missing)}")

    @abstractmethod
    def send(self, message: Message) -> None:
        pass

    @abstractmethod
    def send_control(self, message: Message) -> None:
        pass

    def _send(self, message: Message, addr: Address) -> None:
        if self.transmitter:
            self.transmitter.add_message(message, addr)
            self.last_sent_timestamp = time.monotonic()

    def _send_control(self, message: Message, addr: Address) -> None:
        if self.transmitter:
            self.transmitter.set_control_message(message, addr)
            self.last_sent_timestamp = time.monotonic()

    def heartbeat(self, now: float | None = None) -> None:
        """Send a heartbeat once nothing has gone out for `last_sent_timeout`."""
        if now is None:
            now = time.monotonic()

        if now >= self.heartbeat_deadline():
            self.send(Heartbeat())

    def heartbeat_deadline(self) -> float:
        return self.last_sent_timestamp + self.last_sent_timeout

    def timeout_deadline(self) -> float | None:
        """When the current state times out; None when the state has no timeout."""
        match self.state:
            case State.CONNECTED:
                return self.last_message_timestamp + self.no_message_timeout

            case State.FAILSAFE:
                return self.last_message_timestamp + self.disconnect_timeout

            case _:
                return None

    def wait_until(self, deadline: float) -> None:
        """Sleep until `deadline` on the monotonic clock, `MAXIMUM_WAIT_SECONDS` at most; stop() ends it early."""
        remaining = min(deadline - time.monotonic(), self.MAXIMUM_WAIT_SECONDS)
        self._wake.wait(max(0.0, remaining))
        self._wake.clear()

    def wake(self) -> None:
        self._wake.set()

    def get_last_address(self) -> Address | None:
        if len(self.message_history) > 0:
            return self.message_history[-1][1]

        return None

    def check_timeout(self, now: float | None = None) -> None:
        if now is None:
            now = time.monotonic()

        elapsed = now - self.last_message_timestamp

        match self.state:
            case State.CONNECTED | State.FAILSAFE if elapsed >= self.disconnect_timeout:
                logger.error(f"No message received for {self.disconnect_timeout}s")
                self.handle_state_change(State.DISCONNECTED)

            case State.CONNECTED if elapsed >= self.no_message_timeout:
                self.silence_started_at = self.last_message_timestamp
                self.handle_state_change(State.FAILSAFE)

            case _:
                pass

    def subscribe(self, cls: type[T], handler: Handler[T]) -> None:
        """
        Keep a custom subscription handler, do not rely on the messageHandler
        since it might be re-initialized.
        """
        self.subscriptions[cls].append(handler)

    def on(self, state: State, handler: Callable[[], None]) -> None:
        self.state_handlers[state].append(handler)

    def handle_state_change(self, new_state: State) -> None:
        logger.debug(f"State changed from '{self.state}' to '{new_state}'")
        self.state = new_state

        for current_state, handlers in self.state_handlers.items():
            if current_state == new_state:
                for fn in handlers:
                    fn()

    def all_handler(self, message: Message, addr: Address) -> None:
        """
        All messages are handled here.
        Registered (external) handlers will get messages forwarded from here
        """
        now = time.monotonic()
        if self.state == State.FAILSAFE:
            # The session was never torn down, so the CONNECTED handlers stay
            # quiet; the silence is the one thing worth reporting.
            self.state = State.CONNECTED
            silence = now - self.silence_started_at
            logger.warning(f"Control resumed after {silence:.2f}s without messages")

        self.last_message_timestamp = now
        self.message_history.append(MessageFromAddress(message, addr))
        self.message_history = self.message_history[-self.message_history_length :]

        for cls, handlers in self.subscriptions.items():
            if isinstance(message, cls):
                for fn in handlers:
                    fn(message, addr)

    def start(self) -> None:
        """Override start to validate initialization before starting thread"""
        self.validate_initialization()
        super().start()
