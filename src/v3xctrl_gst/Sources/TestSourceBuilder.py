import logging

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

from .SourceBuilder import SourceBuilder


class TestSourceBuilder(SourceBuilder):
    """Builds videotestsrc with time overlay"""

    NEEDS_SYNC = False  # Live test source, no sync needed

    def build(self, pipeline: Gst.Pipeline) -> Gst.Element:
        """
        Build test source with time overlay.

        Creates videotestsrc with SMPTE pattern and adds a time overlay
        in the center of the frame.

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

        overlay = Gst.ElementFactory.make("timeoverlay", "overlay")
        if not overlay:
            raise RuntimeError("Failed to create timeoverlay")

        overlay.set_property("halignment", "center")
        overlay.set_property("valignment", "center")

        pipeline.add(source)
        pipeline.add(overlay)

        if not source.link(overlay):
            raise RuntimeError("Failed to link videotestsrc to timeoverlay")

        self._output_element = overlay

        logging.info("Created test source with time overlay")

        return source
