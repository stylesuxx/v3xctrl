import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from v3xctrl_telemetry.dataclasses import GpsFix, GpsFixType

logger = logging.getLogger(__name__)

FSYNC_EVERY_POINTS = 10  # a full fsync per point at 1Hz is needless f2fs/SD wear

# GPX only knows none/2d/3d/dgps/pps; NAV-PVT's dead reckoning modes have no equivalent
_GPX_FIX_TYPES = {
    GpsFixType.FIX_2D: "2d",
    GpsFixType.FIX_3D: "3d",
    GpsFixType.GNSS_DEAD_RECKONING: "3d",
}

_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="v3xctrl"
  xmlns="http://www.topografix.com/GPX/1/1"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v2"
  xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd\
 http://www.garmin.com/xmlschemas/TrackPointExtension/v2\
 https://www8.garmin.com/xmlschemas/TrackPointExtensionv2.xsd">
  <metadata>
    <time>{time}</time>
  </metadata>
  <trk>
    <name>{name}</name>
    <trkseg>
"""


def _isoformat(moment: datetime) -> str:
    """GPX wants an xsd:dateTime; Z reads better than the +00:00 isoformat produces."""
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


class GpxWriter:
    """Streams a GPX 1.1 track, writing one complete <trkpt> at a time.

    Knows nothing about fix quality or when to log - it writes what it is given. The file is
    created on the first point, so a vehicle that never gets a fix leaves nothing behind.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._path: Path | None = None
        self._file: TextIO | None = None
        self._segment_open = False
        self._closed = False
        self._points_since_sync = 0

    @property
    def path(self) -> Path | None:
        return self._path

    def add_point(self, fix: GpsFix) -> None:
        if self._closed:
            return

        file = self._file if self._file is not None else self._open()
        if not self._segment_open:
            file.write("    <trkseg>\n")
            self._segment_open = True

        file.write(self._to_trkpt(fix))
        file.flush()

        self._points_since_sync += 1
        if self._points_since_sync >= FSYNC_EVERY_POINTS:
            os.fsync(file.fileno())
            self._points_since_sync = 0

    def break_segment(self) -> None:
        """Signal a coverage gap, so viewers draw no line across it."""
        if self._file is None or not self._segment_open:
            return

        self._file.write("    </trkseg>\n")
        self._file.flush()
        self._segment_open = False

    def close(self) -> None:
        self._closed = True
        if self._file is None:
            return

        if self._segment_open:
            self._file.write("    </trkseg>\n")
            self._segment_open = False

        self._file.write("  </trk>\n</gpx>\n")
        self._file.flush()
        os.fsync(self._file.fileno())
        self._file.close()
        self._file = None

        logger.info("GPX: closed track %s", self._path)

    def _open(self) -> TextIO:
        os.makedirs(self._directory, exist_ok=True)

        # same local-time convention as the stream-*.ts beside it, so the pair is obvious
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self._path = self._directory / f"track-{timestamp}.gpx"

        # newline is pinned so a file written on Windows during tests matches the Pi's
        file = self._path.open("w", encoding="utf-8", newline="\n")
        file.write(_HEADER.format(time=_isoformat(datetime.now(UTC)), name=self._path.stem))

        self._file = file
        self._segment_open = True
        logger.info("GPX: opened track %s", self._path)

        return file

    @staticmethod
    def _to_trkpt(fix: GpsFix) -> str:
        """Child order is fixed by the GPX 1.1 schema sequence, not a preference."""
        return (
            f'      <trkpt lat="{fix.lat:.7f}" lon="{fix.lng:.7f}">\n'
            f"        <ele>{fix.altitude:.2f}</ele>\n"
            f"        <time>{_isoformat(datetime.now(UTC))}</time>\n"
            f"        <fix>{_GPX_FIX_TYPES.get(fix.fix_type, 'none')}</fix>\n"
            f"        <sat>{fix.satellites}</sat>\n"
            f"        <pdop>{fix.pdop:.2f}</pdop>\n"
            f"        <extensions>\n"
            f"          <gpxtpx:TrackPointExtension>\n"
            f"            <gpxtpx:speed>{fix.ground_speed:.2f}</gpxtpx:speed>\n"
            f"            <gpxtpx:course>{fix.heading:.1f}</gpxtpx:course>\n"
            f"          </gpxtpx:TrackPointExtension>\n"
            f"        </extensions>\n"
            f"      </trkpt>\n"
        )
