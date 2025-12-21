import logging

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

from .SourceBuilder import SourceBuilder


class FileSourceBuilder(SourceBuilder):
    """Builds file source with demux/decode chain"""

    NEEDS_SYNC = True  # File source needs sync for real-time playback

    def build(self, pipeline: Gst.Pipeline) -> Gst.Element:
        """
        Build file source bin with demuxer, decoder, and timing control.

        Creates a bin containing:
        - filesrc -> qtdemux -> h264parse -> avdec_h264 -> videoconvert -> videorate -> identity

        Args:
            pipeline: GStreamer pipeline to add the bin to

        Returns:
            The source bin element
        """
        bin_name = "file_source_bin"
        source_bin = Gst.Bin.new(bin_name)

        filesrc = Gst.ElementFactory.make("filesrc", "filesrc")
        if not filesrc:
            raise RuntimeError("Failed to create filesrc")

        file_location = self.settings.get('file_src')
        if not file_location:
            raise ValueError("file_src setting is required for FileSourceBuilder")

        filesrc.set_property("location", file_location)

        demux = Gst.ElementFactory.make("qtdemux", "demux")
        if not demux:
            raise RuntimeError("Failed to create qtdemux")

        h264parse = Gst.ElementFactory.make("h264parse", "h264parse")
        if not h264parse:
            raise RuntimeError("Failed to create h264parse")

        decoder = Gst.ElementFactory.make("avdec_h264", "decoder")
        if not decoder:
            raise RuntimeError("Failed to create avdec_h264")

        videoconvert = Gst.ElementFactory.make("videoconvert", "videoconvert")
        if not videoconvert:
            raise RuntimeError("Failed to create videoconvert")

        videorate = Gst.ElementFactory.make("videorate", "videorate")
        if not videorate:
            raise RuntimeError("Failed to create videorate")

        videorate.set_property("drop-only", False)
        videorate.set_property("skip-to-first", True)

        identity = Gst.ElementFactory.make("identity", "identity")
        if not identity:
            raise RuntimeError("Failed to create identity")

        identity.set_property("sync", True)

        for element in [
            filesrc,
            demux,
            h264parse,
            decoder,
            videoconvert,
            videorate,
            identity
        ]:
            source_bin.add(element)

        if not filesrc.link(demux):
            raise RuntimeError("Failed to link filesrc to demux")

        def on_demux_pad_added(element, pad):
            """Callback for when demuxer creates a pad"""
            pad_name = pad.get_name()
            logging.info(f"Demux pad added: {pad_name}")

            if pad_name.startswith("video_"):
                sink_pad = h264parse.get_static_pad("sink")
                if not sink_pad.is_linked():
                    ret = pad.link(sink_pad)
                    if ret != Gst.PadLinkReturn.OK:
                        logging.error(f"Failed to link demux to h264parse: {ret}")

        demux.connect("pad-added", on_demux_pad_added)

        if not h264parse.link(decoder):
            raise RuntimeError("Failed to link h264parse to decoder")

        if not decoder.link(videoconvert):
            raise RuntimeError("Failed to link decoder to videoconvert")

        if not videoconvert.link(videorate):
            raise RuntimeError("Failed to link videoconvert to videorate")

        if not videorate.link(identity):
            raise RuntimeError("Failed to link videorate to identity")

        identity_src = identity.get_static_pad("src")
        ghost_pad = Gst.GhostPad.new("src", identity_src)
        source_bin.add_pad(ghost_pad)

        pipeline.add(source_bin)

        self._output_element = source_bin

        logging.info(f"Created file source from: {file_location}")

        return source_bin
