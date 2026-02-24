import logging
import time

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

from .SourceBuilder import SourceBuilder  # noqa: E402

logger = logging.getLogger(__name__)


class TestSourceBuilder(SourceBuilder):
    """Builds videotestsrc with epoch timestamp overlay for latency measurement"""

    NEEDS_SYNC = False  # Live test source, no sync needed

    def build(self, pipeline: Gst.Pipeline) -> Gst.Element:
        """
        Build test source with epoch timestamp overlay.

        Creates videotestsrc with SMPTE pattern and overlays the current
        UTC wall-clock time with millisecond precision. Each frame is
        timestamped via a pad probe.

        Args:
            pipeline: GStreamer pipeline to add elements to

        Returns:
            The videotestsrc element
        """
        source = Gst.ElementFactory.make("videotestsrc", "testsrc")
        if not source:
            raise RuntimeError("Failed to create videotestsrc")

        source.set_property("is-live", True)
        source.set_property("pattern", "smpte")

        overlay = Gst.ElementFactory.make("textoverlay", "overlay")
        if not overlay:
            raise RuntimeError("Failed to create textoverlay")

        overlay.set_property("halignment", "center")
        overlay.set_property("valignment", "center")

        pipeline.add(source)
        pipeline.add(overlay)

        if not source.link(overlay):
            raise RuntimeError("Failed to link videotestsrc to textoverlay")

        # Stamp each frame with wall-clock time
        sink_pad = overlay.get_static_pad("video_sink")
        sink_pad.add_probe(Gst.PadProbeType.BUFFER, self._on_buffer, overlay)

        self._output_element = overlay

        return source

    @staticmethod
    def _on_buffer(pad, info, overlay):
        now = time.time()
        ms = int(now * 1000) % 1000
        t = time.gmtime(int(now))
        overlay.set_property(
            "text",
            f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}.{ms:03d}"
        )

        return Gst.PadProbeReturn.OK
