"""
Generic thread wrapper that drives a TelemetrySource at a fixed interval.

Each collector owns one source and one store_updater callable. The loop:

    1. source.update()                       # I/O happens here, no lock held
    2. store_updater(source.get_state())     # store acquires its own lock briefly

Exceptions from either call are logged and the thread continues - one bad read
must never kill the collector.
"""

import logging
import threading
from collections.abc import Callable
from typing import Any

from v3xctrl_telemetry.TelemetrySource import TelemetrySource

logger = logging.getLogger(__name__)


class TelemetryCollector(threading.Thread):
    def __init__(
        self,
        name: str,
        source: TelemetrySource,
        store_updater: Callable[[Any], None],
        interval: float,
    ) -> None:
        super().__init__(daemon=True, name=f"telemetry-{name}")
        self._source_name = name
        self._source = source
        self._store_updater = store_updater
        self._interval = interval
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._source.update()
                self._store_updater(self._source.get_state())
            except Exception:
                logger.exception("Telemetry source %r raised during update", self._source_name)
            self._stop_event.wait(self._interval)

    def stop(self) -> None:
        self._stop_event.set()
