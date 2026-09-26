import logging
import threading
import time
from collections.abc import Callable

from v3xctrl_ui.core.dataclasses import ApplicationModel

logger = logging.getLogger(__name__)

# Floor for the send interval, so a zero or absurd rate cannot spin the thread
MINIMUM_INTERVAL_SECONDS = 0.005


class ControlSender(threading.Thread):
    """Sends the latest control values at the configured rate.

    The render loop hands over throttle and steering whenever it runs; the
    cadence on the wire is this thread's own, so a slow frame does not stretch
    the gap between two control messages.
    """

    def __init__(
        self,
        model: ApplicationModel,
        send: Callable[[float, float], None],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(daemon=True, name="control-sender")
        self._model = model
        self._send = send
        self._clock = clock
        self._lock = threading.Lock()
        self._throttle = 0.0
        self._steering = 0.0
        self._stop_event = threading.Event()
        self._warned_send_failure = False

    def set_values(self, throttle: float, steering: float) -> None:
        with self._lock:
            self._throttle = throttle
            self._steering = steering

    def run_once(self, now: float) -> float:
        """Send once if the user is connected; return the time of the next send."""
        if self._model.user_connected:
            with self._lock:
                throttle, steering = self._throttle, self._steering

            try:
                self._send(throttle, steering)
                self._warned_send_failure = False
            except Exception as error:
                if not self._warned_send_failure:
                    logger.warning(f"Control send failed: {error}")
                    self._warned_send_failure = True

        return now + max(self._model.control_interval, MINIMUM_INTERVAL_SECONDS)

    def run(self) -> None:
        while not self._stop_event.is_set():
            deadline = self.run_once(self._clock())
            self._stop_event.wait(max(0.0, deadline - self._clock()))

    def stop(self) -> None:
        self._stop_event.set()
