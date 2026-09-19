"""
Generic thread wrapper that owns one TelemetrySource and drives it at a fixed rate.

The collector owns the whole lifecycle of its source. Each tick:

    1. factory()                             # first tick, and after a rebuild
    2. source.update()                       # I/O happens here, no lock held
    3. store_updater(source.get_state())     # store acquires its own lock briefly

Construction happens on the collector thread, so a slow or absent device never delays
startup, and it is retried on a backoff for as long as the collector runs. A source that
fails `REBUILD_AFTER_FAILURES` updates in a row is discarded and rebuilt, which covers a
device that disappears at runtime.

While a source is unavailable the store holds `unavailable_state`, so the payload reports
defaults rather than the last reading from before the sensor died.

`run_once()` is the loop body: tests drive it directly to assert retry and rebuild
behaviour without threads or sleeps.
"""

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from v3xctrl_telemetry.TelemetrySource import TelemetrySource

logger = logging.getLogger(__name__)


class TelemetryCollector(threading.Thread):
    REBUILD_AFTER_FAILURES = 3
    MAX_RETRY_INTERVAL_S = 30.0

    def __init__(
        self,
        name: str,
        factory: Callable[[], Any],
        unavailable_state: Any,
        store_updater: Callable[[Any], None],
        interval: float,
    ) -> None:
        super().__init__(daemon=True, name=f"telemetry-{name}")
        self._source_name = name
        self._factory = factory
        self._unavailable_state = unavailable_state
        self._store_updater = store_updater
        self._interval = interval
        self._stop_event = threading.Event()

        self._source: TelemetrySource | None = None
        self._consecutive_failures = 0
        self._retry_interval = min(interval, self.MAX_RETRY_INTERVAL_S)
        self._next_attempt = 0.0
        self._warned_unavailable = False
        self._warned_failing = False
        self._warned_loop_error = False

    def run(self) -> None:
        while not self._stop_event.is_set():
            now = time.monotonic()
            try:
                deadline = self.run_once(now)

            except Exception:
                if not self._warned_loop_error:
                    logger.exception("Telemetry collector %r raised", self._source_name)
                    self._warned_loop_error = True
                deadline = now + self._interval

            self._stop_event.wait(max(0.0, deadline - time.monotonic()))

    def stop(self) -> None:
        self._stop_event.set()

    def run_once(self, now: float) -> float:
        """Advance by one tick. Returns the monotonic deadline for the next call."""
        if self._source is None:
            if now < self._next_attempt:
                return self._next_attempt

            self._construct_source(now)
            if self._source is None:
                return self._next_attempt

        self._poll_source(now)
        if self._source is None:
            return self._next_attempt

        return now + self._interval

    def _construct_source(self, now: float) -> None:
        try:
            self._source = self._factory()

        except Exception as exc:
            self._schedule_retry(now)
            if not self._warned_unavailable:
                logger.warning("Telemetry source %r unavailable: %s", self._source_name, exc)
                self._warned_unavailable = True

            return

        self._consecutive_failures = 0

    def _poll_source(self, now: float) -> None:
        source = self._source
        if source is None:
            return

        try:
            source.update()
            state = source.get_state()

        except Exception as exc:
            if not self._warned_failing:
                logger.warning("Telemetry source %r failing: %s", self._source_name, exc)
                self._warned_failing = True

            self._consecutive_failures += 1
            if self._consecutive_failures >= self.REBUILD_AFTER_FAILURES:
                self._discard_source(now)

            return

        # Data reaching the store is what proves recovery
        if self._warned_unavailable or self._warned_failing:
            logger.info("Telemetry source %r recovered", self._source_name)
            self._warned_unavailable = False
            self._warned_failing = False

        self._consecutive_failures = 0
        self._store_updater(state)

    def _discard_source(self, now: float) -> None:
        self._source = None
        self._consecutive_failures = 0
        self._retry_interval = min(self._interval, self.MAX_RETRY_INTERVAL_S)
        self._schedule_retry(now)
        self._store_updater(self._unavailable_state)

    def _schedule_retry(self, now: float) -> None:
        self._next_attempt = now + self._retry_interval
        self._retry_interval = min(self._retry_interval * 2, self.MAX_RETRY_INTERVAL_S)
