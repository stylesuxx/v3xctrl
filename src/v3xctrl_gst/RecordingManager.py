"""
Manages dynamic recording branch for a GStreamer pipeline.

Handles adding/removing recording elements to/from a running pipeline
via a tee element.
"""
import logging
import os
import threading
from datetime import datetime
from typing import Callable, Dict, Optional, Any

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib


class RecordingManager:
    STOP_TIMEOUT = 5.0

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
        self._stop_complete: Optional[threading.Event] = None

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

        # Set flag early so telemetry reflects the change immediately
        # while the pipeline is being built. Reverted on failure.
        self._is_recording = True

        os.makedirs(self._recording_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        filename = f"{self._recording_dir}/stream-{timestamp}.ts"

        queue_rec = Gst.ElementFactory.make("queue", "queue_rec")
        if not queue_rec:
            logging.error("Failed to create recording queue")
            self._is_recording = False
            return False

        queue_rec.set_property("max-size-buffers", self._sizebuffers)
        queue_rec.set_property("leaky", 2)  # Downstream
        if self._on_queue_overrun:
            queue_rec.connect("overrun", self._on_queue_overrun)

        parser = Gst.ElementFactory.make("h264parse", "parser")
        if not parser:
            logging.error("Failed to create h264parse")
            self._is_recording = False
            return False

        muxer = Gst.ElementFactory.make("mpegtsmux", "muxer")
        if not muxer:
            logging.error("Failed to create mpegtsmux")
            self._is_recording = False
            return False

        filesink = Gst.ElementFactory.make("filesink", "filesink")
        if not filesink:
            logging.error("Failed to create filesink")
            self._is_recording = False
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

        logging.info(f"Recording started: {filename}")

        return True

    def stop(self) -> bool:
        """
        Dynamically stop recording by removing the recording branch from the pipeline.

        Uses a blocking pad probe on the tee's src pad to ensure no buffer is
        in-flight when the branch is torn down. This prevents the tee from
        blocking the main pipeline (including the UDP video branch).

        Returns:
            True if recording stopped successfully, False otherwise
        """
        if not self._is_recording:
            logging.warning("Recording is not active")
            return False

        if not self._tee_pad:
            logging.error("Tee pad not available for recording stop")
            return False

        # Set flag early so telemetry reflects the change immediately
        # while the pipeline is being torn down.
        self._is_recording = False

        self._stop_complete = threading.Event()

        self._tee_pad.add_probe(
            Gst.PadProbeType.BLOCK_DOWNSTREAM,
            self._on_tee_pad_blocked
        )

        if not self._stop_complete.wait(timeout=self.STOP_TIMEOUT):
            logging.error("Recording stop timed out, forcing teardown")
            self._force_teardown()

        return True

    def _on_tee_pad_blocked(self, pad, info):
        """
        Probe callback invoked on the streaming thread when the tee's src pad
        is blocked. No buffer is in-flight to the recording branch, so it is
        safe to unlink and send EOS.
        """
        # Unlink from tee — the main pipeline can continue pushing to other
        # branches (UDP) without being affected by the recording teardown.
        queue_sink_pad = self._elements['queue'].get_static_pad("sink")
        if queue_sink_pad:
            pad.unlink(queue_sink_pad)

        self._tee.release_request_pad(pad)
        self._tee_pad = None

        # Send EOS to flush remaining buffered data through the recording
        # branch so the muxer can finalize the file properly.
        if queue_sink_pad:
            queue_sink_pad.send_event(Gst.Event.new_eos())

        # Listen for EOS on filesink to know when flushing is complete
        filesink = self._elements.get('filesink')
        if filesink:
            filesink_pad = filesink.get_static_pad("sink")
            if filesink_pad:
                filesink_pad.add_probe(
                    Gst.PadProbeType.EVENT_DOWNSTREAM,
                    self._on_recording_eos
                )
            else:
                GLib.idle_add(self._teardown)
        else:
            GLib.idle_add(self._teardown)

        return Gst.PadProbeReturn.REMOVE

    def _on_recording_eos(self, pad, info):
        """
        Probe callback invoked when an event reaches the filesink's sink pad.
        When EOS arrives, the muxer has finalized the file and we can safely
        tear down the recording elements.
        """
        event = info.get_event()
        if event.type != Gst.EventType.EOS:
            return Gst.PadProbeReturn.PASS

        GLib.idle_add(self._teardown)
        return Gst.PadProbeReturn.REMOVE

    def _teardown(self):
        """Remove recording elements from the pipeline. Runs on main thread."""
        for name, element in self._elements.items():
            if name == 'filename':
                continue
            if isinstance(element, Gst.Element):
                element.set_state(Gst.State.NULL)
                self._pipeline.remove(element)

        filename = self._elements.get('filename', 'unknown')
        logging.info(f"Recording stopped: {filename}")

        self._elements = {}

        if self._stop_complete:
            self._stop_complete.set()

        return False

    def _force_teardown(self):
        """Fallback teardown when the probe-based approach times out."""
        if self._tee_pad:
            queue = self._elements.get('queue')
            if queue:
                queue_sink_pad = queue.get_static_pad("sink")
                if queue_sink_pad:
                    self._tee_pad.unlink(queue_sink_pad)
            self._tee.release_request_pad(self._tee_pad)
            self._tee_pad = None

        for name, element in self._elements.items():
            if name == 'filename':
                continue
            if isinstance(element, Gst.Element):
                element.set_state(Gst.State.NULL)
                if element.get_parent():
                    self._pipeline.remove(element)

        filename = self._elements.get('filename', 'unknown')
        logging.warning(f"Recording stopped (forced): {filename}")

        self._elements = {}

    def _cleanup(self) -> None:
        """Clean up recording elements if setup fails."""
        self._is_recording = False

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
