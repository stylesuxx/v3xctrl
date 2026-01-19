"""
Manages dynamic recording branch for a GStreamer pipeline.

Handles adding/removing recording elements to/from a running pipeline
via a tee element.
"""
import logging
import os
from datetime import datetime
from typing import Callable, Dict, Optional, Any

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst


class RecordingManager:
    def __init__(
        self,
        pipeline: Gst.Pipeline,
        tee: Gst.Element,
        recording_dir: str,
        sizebuffers: int = 30,
        on_queue_overrun: Optional[Callable[[Gst.Element], None]] = None
    ) -> None:
        self._pipeline = pipeline
        self._tee = tee
        self._recording_dir = recording_dir
        self._sizebuffers = sizebuffers
        self._on_queue_overrun = on_queue_overrun

        self._is_recording = False
        self._elements: Dict[str, Any] = {}
        self._tee_pad: Optional[Gst.Pad] = None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start(self) -> bool:
        """
        Dynamically start recording by adding a recording branch to the pipeline.

        Returns:
            True if recording started successfully, False otherwise
        """
        if self._is_recording:
            logging.warning("Recording is already active")
            return False

        if not self._recording_dir:
            logging.error("Recording directory not configured")
            return False

        os.makedirs(self._recording_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        filename = f"{self._recording_dir}/stream-{timestamp}.ts"

        queue_rec = Gst.ElementFactory.make("queue", "queue_rec")
        if not queue_rec:
            logging.error("Failed to create recording queue")
            return False

        queue_rec.set_property("max-size-buffers", self._sizebuffers)
        queue_rec.set_property("leaky", 2)  # Downstream
        if self._on_queue_overrun:
            queue_rec.connect("overrun", self._on_queue_overrun)

        parser = Gst.ElementFactory.make("h264parse", "parser")
        if not parser:
            logging.error("Failed to create h264parse")
            return False

        muxer = Gst.ElementFactory.make("mpegtsmux", "muxer")
        if not muxer:
            logging.error("Failed to create mpegtsmux")
            return False

        filesink = Gst.ElementFactory.make("filesink", "filesink")
        if not filesink:
            logging.error("Failed to create filesink")
            return False

        filesink.set_property("location", filename)
        filesink.set_property("sync", False)
        filesink.set_property("async", False)

        self._elements = {
            'queue': queue_rec,
            'parser': parser,
            'muxer': muxer,
            'filesink': filesink,
            'filename': filename
        }

        self._pipeline.add(queue_rec)
        self._pipeline.add(parser)
        self._pipeline.add(muxer)
        self._pipeline.add(filesink)

        tee_src_pad = self._tee.request_pad_simple("src_%u")
        if not tee_src_pad:
            logging.error("Failed to request pad from tee")
            self._cleanup()
            return False

        self._tee_pad = tee_src_pad

        queue_sink_pad = queue_rec.get_static_pad("sink")
        if tee_src_pad.link(queue_sink_pad) != Gst.PadLinkReturn.OK:
            logging.error("Failed to link tee to queue_rec")
            self._cleanup()
            return False

        if not queue_rec.link(parser):
            logging.error("Failed to link queue_rec to parser")
            self._cleanup()
            return False

        if not parser.link(muxer):
            logging.error("Failed to link parser to muxer")
            self._cleanup()
            return False

        if not muxer.link(filesink):
            logging.error("Failed to link muxer to filesink")
            self._cleanup()
            return False

        queue_rec.sync_state_with_parent()
        parser.sync_state_with_parent()
        muxer.sync_state_with_parent()
        filesink.sync_state_with_parent()

        self._is_recording = True
        logging.info(f"Recording started: {filename}")

        return True

    def stop(self) -> bool:
        """
        Dynamically stop recording by removing the recording branch from the pipeline.

        Returns:
            True if recording stopped successfully, False otherwise
        """
        if not self._is_recording:
            logging.warning("Recording is not active")
            return False

        # Send EOS to the recording queue to flush all buffers
        queue_rec = self._elements.get('queue')
        if queue_rec:
            queue_rec_pad = queue_rec.get_static_pad("sink")
            if queue_rec_pad:
                queue_rec_pad.send_event(Gst.Event.new_eos())

        # Set recording elements to NULL state
        # This blocks until EOS is processed and all buffers are flushed
        for name, element in self._elements.items():
            if name == 'filename':
                continue
            if isinstance(element, Gst.Element):
                element.set_state(Gst.State.NULL)

        # Unlink and release the tee pad
        if self._tee_pad:
            queue_sink_pad = self._elements['queue'].get_static_pad("sink")
            if queue_sink_pad:
                self._tee_pad.unlink(queue_sink_pad)

            self._tee.release_request_pad(self._tee_pad)
            self._tee_pad = None

        # Remove elements from pipeline
        for name, element in self._elements.items():
            if name == 'filename':
                continue
            if isinstance(element, Gst.Element):
                self._pipeline.remove(element)

        filename = self._elements.get('filename', 'unknown')
        logging.info(f"Recording stopped: {filename}")

        self._elements = {}
        self._is_recording = False

        return True

    def _cleanup(self) -> None:
        """Clean up recording elements if setup fails."""
        if self._tee_pad:
            self._tee.release_request_pad(self._tee_pad)
            self._tee_pad = None

        for name, element in self._elements.items():
            if name == 'filename':
                continue
            if isinstance(element, Gst.Element):
                element.set_state(Gst.State.NULL)
                if element.get_parent():
                    self._pipeline.remove(element)

        self._elements = {}
