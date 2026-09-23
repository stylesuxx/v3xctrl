import logging

from v3xctrl_telemetry.dataclasses import LocationInfo
from v3xctrl_telemetry.GpsTelemetry import GpsTelemetry
from v3xctrl_telemetry.GpsTrackLogger import GpsTrackLogger

logger = logging.getLogger(__name__)


class TrackLoggingGps:
    """Feeds every new fix from the wrapped GPS to a track logger.

    The logger is owned by `Telemetry`, not by this wrapper: the collector rebuilds its source
    when the device disappears, and the open track has to outlive that.

    `update()` drains every pending NAV-PVT but `get_fix()` only returns the last, so if the
    collector falls behind, intermediate fixes are skipped. Harmless, points are decimated to
    1Hz anyway.
    """

    def __init__(self, gps: GpsTelemetry, track_logger: GpsTrackLogger) -> None:
        self._gps = gps
        self._track_logger = track_logger
        self._warned = False

    def update(self) -> bool:
        updated = self._gps.update()

        # a poll that read nothing still returns the previous fix, which must not count twice
        fix = self._gps.get_fix()
        if not updated or fix is None:
            return updated

        # the collector treats any exception as a GPS failure and tears the source down, so a
        # full disk would otherwise take live GPS telemetry with it
        try:
            self._track_logger.add_fix(fix)
        except OSError as exc:
            if not self._warned:
                logger.warning("GPS track: writing failed, telemetry unaffected: %s", exc)
                self._warned = True

            return updated

        if self._warned:
            logger.info("GPS track: writing recovered")
            self._warned = False

        return updated

    def get_state(self) -> LocationInfo:
        return self._gps.get_state()
