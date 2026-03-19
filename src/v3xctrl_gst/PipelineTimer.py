import logging
import time

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

logger = logging.getLogger(__name__)


class PipelineTimer:
    """Measures per-frame timing through the GStreamer pipeline stages.

    Tracks timing data at four probe points (source, capsfilter, encoder, UDP)
    and periodically logs aggregate statistics. Designed to be owned by Streamer
    and called from its pad probe callbacks.
    """

    def __init__(self, log_interval: float = 1.0) -> None:
        self._enabled = False
        self._log_interval = log_interval
        self._last_log = 0.0

        self._data: dict[int, dict[str, float]] = {}
        self._stats: dict[str, list[float]] = self._empty_stats()
        self._debug: dict[str, int] = self._empty_debug()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True
        self._data.clear()
        self._stats = self._empty_stats()
        self._debug = self._empty_debug()
        self._last_log = time.monotonic()

    def disable(self) -> None:
        self._enabled = False

    def on_source_buffer(self, pts: int, pipeline: Gst.Pipeline) -> None:
        if not self._enabled:
            return

        now = time.monotonic()
        self._debug["source_probe"] += 1

        running_time = pipeline.get_clock().get_time() - pipeline.get_base_time()
        capture_delay = (running_time - pts) / Gst.MSECOND

        self._data[pts] = {
            "source": now,
            "capture_delay": capture_delay,
        }

    def on_capsfilter_buffer(self, pts: int) -> None:
        if not self._enabled:
            return

        self._debug["capsfilter_probe"] += 1
        if pts in self._data:
            self._data[pts]["capsfilter"] = time.monotonic()
        else:
            self._debug["capsfilter_miss"] += 1

    def on_encoder_buffer(self, pts: int) -> None:
        if not self._enabled:
            return

        self._debug["encoder_probe"] += 1
        if pts in self._data:
            self._data[pts]["encoder"] = time.monotonic()
        else:
            self._debug["encoder_miss"] += 1

    def on_udp_buffer(self, pts: int) -> None:
        if not self._enabled:
            return

        if pts not in self._data:
            self._debug["udp_miss"] += 1
            return

        timing = self._data[pts]
        self._debug["udp_probe"] += 1

        if "source" not in timing or "capsfilter" not in timing or "encoder" not in timing:
            self._debug["incomplete"] += 1
            return

        now = time.monotonic()
        self._data.pop(pts)

        capture_time = timing.get("capture_delay", 0)
        capsfilter_time = (timing["capsfilter"] - timing["source"]) * 1000
        encode_time = (timing["encoder"] - timing["capsfilter"]) * 1000
        package_time = (now - timing["encoder"]) * 1000

        self._stats["capture"].append(capture_time)
        self._stats["capsfilter"].append(capsfilter_time)
        self._stats["encode"].append(encode_time)
        self._stats["package"].append(package_time)

        if now - self._last_log >= self._log_interval:
            self._log_stats()
            self._last_log = now

        if len(self._data) > 100:
            oldest_pts = min(self._data.keys())
            del self._data[oldest_pts]

    def _log_stats(self) -> None:
        if not self._stats["capture"]:
            return

        def stats(data: list[float]) -> tuple[float, float, float]:
            if not data:
                return 0.0, 0.0, 0.0
            return min(data), sum(data) / len(data), max(data)

        _cap_min, cap_avg, _cap_max = stats(self._stats["capture"])
        _enc_min, enc_avg, _enc_max = stats(self._stats["encode"])
        _pkg_min, pkg_avg, _pkg_max = stats(self._stats["package"])

        total_avg = cap_avg + enc_avg + pkg_avg
        frame_count = len(self._stats["capture"])
        interval = time.monotonic() - self._last_log
        fps = frame_count / interval if interval > 0 else 0

        logger.debug(
            f"[TIMING] capture: {cap_avg:.1f}ms | "
            f"encode: {enc_avg:.1f}ms | "
            f"total: {total_avg:.1f}ms | "
            f"fps: {fps:.1f} ({frame_count} frames)"
        )

        self._debug = self._empty_debug()
        self._stats = self._empty_stats()

    @staticmethod
    def _empty_stats() -> dict[str, list[float]]:
        return {
            "capture": [],
            "capsfilter": [],
            "encode": [],
            "package": [],
        }

    @staticmethod
    def _empty_debug() -> dict[str, int]:
        return {
            "source_probe": 0,
            "capsfilter_probe": 0,
            "capsfilter_miss": 0,
            "encoder_probe": 0,
            "encoder_miss": 0,
            "udp_probe": 0,
            "udp_miss": 0,
            "incomplete": 0,
        }
