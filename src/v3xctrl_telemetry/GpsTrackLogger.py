import logging
import threading
import time
from pathlib import Path

from v3xctrl_helper import haversine_meters
from v3xctrl_telemetry.dataclasses import GpsFix, GpsFixType, GpsTrackMode
from v3xctrl_telemetry.GpxWriter import GpxWriter

logger = logging.getLogger(__name__)


class GpsTrackLogger:
    """Decides which fixes are good enough to become track points.

    Called from three threads - GPS collector, gst collector and the shutdown path - so every
    public method takes the same lock.
    """

    ARM_FIXES = 5  # one second of settled fix at 5Hz keeps the cold-start wander out
    DROP_FIXES = 3  # a single bad fix must not tear the track
    HEARTBEAT_SECONDS = 15.0  # a parked vehicle still shows up in the timeline

    def __init__(
        self,
        directory: Path,
        mode: GpsTrackMode,
        min_satellites: int,
        interval: float,
        min_distance: float,
    ) -> None:
        self._directory = directory
        self._mode = mode
        self._min_satellites = min_satellites
        self._interval = interval
        self._min_distance = min_distance

        self._lock = threading.Lock()
        self._writer: GpxWriter | None = None
        self._recording = False
        self._closed = False

        self._armed = False
        self._good_streak = 0
        self._bad_streak = 0
        self._last_point: GpsFix | None = None
        self._last_point_at = 0.0

    def set_recording(self, recording: bool) -> None:
        with self._lock:
            if recording == self._recording:
                return

            self._recording = recording
            if not recording and self._mode is GpsTrackMode.WITH_RECORDING:
                self._close_writer()

    def add_fix(self, fix: GpsFix) -> None:
        with self._lock:
            if self._closed:
                return

            good = (
                fix.fix_type >= GpsFixType.FIX_3D
                and fix.fix_ok
                and fix.position_valid
                and fix.satellites >= self._min_satellites
            )
            if good:
                self._good_streak += 1
                self._bad_streak = 0
            else:
                self._bad_streak += 1
                self._good_streak = 0

            if not self._armed and self._good_streak >= self.ARM_FIXES:
                self._armed = True
                self._last_point = None
                logger.info("GPS track: armed (%d satellites)", fix.satellites)
            elif self._armed and self._bad_streak >= self.DROP_FIXES:
                self._armed = False
                logger.info("GPS track: disarmed, fix degraded")
                if self._writer is not None:
                    self._writer.break_segment()

            if not good or not self._armed or not self._is_active():
                return

            now = time.monotonic()
            if not self._is_due(fix, now):
                return

            if self._writer is None:
                self._writer = GpxWriter(self._directory)

            self._writer.add_point(fix)
            self._last_point = fix
            self._last_point_at = now

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._close_writer()

    def _is_active(self) -> bool:
        match self._mode:
            case GpsTrackMode.OFF:
                return False
            case GpsTrackMode.ALWAYS:
                return True
            case GpsTrackMode.WITH_RECORDING:
                return self._recording

    def _is_due(self, fix: GpsFix, now: float) -> bool:
        if self._last_point is None:
            return True

        # monotonic, so an NTP step early in a run cannot make this negative
        elapsed = now - self._last_point_at
        if elapsed < self._interval:
            return False

        if elapsed >= self.HEARTBEAT_SECONDS:
            return True

        last = self._last_point
        return haversine_meters(last.lat, last.lng, fix.lat, fix.lng) >= self._min_distance

    def _close_writer(self) -> None:
        if self._writer is None:
            return

        self._writer.close()
        self._writer = None
        self._last_point = None
