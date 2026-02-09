import logging
import threading
import time
from typing import Callable, Optional

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
from gi.repository import Gst, GLib, GstApp

import numpy as np

from v3xctrl_ui.network.video.Receiver import Receiver


class ReceiverGst(Receiver):
    """
    GStreamer-based video receiver implementation.

    Uses a GStreamer pipeline with appsink to receive and decode H.264 video
    over RTP/UDP. Generally provides lower latency than PyAV-based receiver.
    """

    def __init__(
        self,
        port: int,
        keep_alive: Callable[[], None],
        log_interval: int = 10,
        history_size: int = 100,
        max_frame_age_ms: int = 500,
        render_ratio: int = 0,
    ) -> None:
        super().__init__(
            port,
            keep_alive,
            log_interval,
            history_size,
            max_frame_age_ms,
            render_ratio
        )

        Gst.init(None)

        self.pipeline: Optional[Gst.Pipeline] = None
        self.appsink: Optional[GstApp.AppSink] = None
        self.loop: Optional[GLib.MainLoop] = None

        self.latest_pts: Optional[int] = None
        self.consecutive_old_frames = 0
        self.max_consecutive_old_frames = 60

        self.last_frame_time: float = 0.0

        # Cached frame dimensions and pre-allocated buffer
        self._cached_width: int = 0
        self._cached_height: int = 0
        self._frame_array: Optional[np.ndarray] = None

    def _setup(self) -> None:
        """Setup GStreamer pipeline."""
        pass

    def _build_pipeline(self) -> bool:
        """Build and configure the GStreamer pipeline dynamically."""
        self.pipeline = Gst.Pipeline.new("receiver-pipeline")
        if not self.pipeline:
            logging.error("Failed to create pipeline")
            return False

        # UDP source
        udpsrc = Gst.ElementFactory.make("udpsrc", "udpsrc")
        if not udpsrc:
            logging.error("Failed to create udpsrc")
            return False

        udpsrc.set_property("port", self.port)
        caps = Gst.Caps.from_string(
            "application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000"
        )
        udpsrc.set_property("caps", caps)

        # RTP jitter buffer
        jitterbuffer = Gst.ElementFactory.make("rtpjitterbuffer", "jitterbuffer")
        if not jitterbuffer:
            logging.error("Failed to create rtpjitterbuffer")
            return False

        jitterbuffer.set_property("latency", 0)
        jitterbuffer.set_property("drop-on-latency", True)

        # RTP H264 depayloader
        depay = Gst.ElementFactory.make("rtph264depay", "depay")
        if not depay:
            logging.error("Failed to create rtph264depay")
            return False

        # H264 parser
        h264parse = Gst.ElementFactory.make("h264parse", "h264parse")
        if not h264parse:
            logging.error("Failed to create h264parse")
            return False

        # H264 decoder
        decoder = Gst.ElementFactory.make("avdec_h264", "decoder")
        if not decoder:
            logging.error("Failed to create avdec_h264")
            return False

        decoder.set_property("output-corrupt", False)
        decoder.set_property("max-threads", 2)

        # Video converter
        videoconvert = Gst.ElementFactory.make("videoconvert", "videoconvert")
        if not videoconvert:
            logging.error("Failed to create videoconvert")
            return False

        # Caps filter for RGB output
        capsfilter = Gst.ElementFactory.make("capsfilter", "capsfilter")
        if not capsfilter:
            logging.error("Failed to create capsfilter")
            return False

        rgb_caps = Gst.Caps.from_string("video/x-raw,format=RGB")
        capsfilter.set_property("caps", rgb_caps)

        # App sink
        self.appsink = Gst.ElementFactory.make("appsink", "sink")
        if not self.appsink:
            logging.error("Failed to create appsink")
            return False

        self.appsink.set_property("emit-signals", True)
        self.appsink.set_property("max-buffers", 1)
        self.appsink.set_property("drop", True)
        self.appsink.set_property("sync", False)
        self.appsink.connect("new-sample", self._on_new_sample)

        # Add elements to pipeline
        elements = [
            udpsrc, jitterbuffer, depay, h264parse,
            decoder, videoconvert, capsfilter, self.appsink
        ]

        for element in elements:
            self.pipeline.add(element)

        # Link elements
        if not udpsrc.link(jitterbuffer):
            logging.error("Failed to link udpsrc to jitterbuffer")
            return False

        if not jitterbuffer.link(depay):
            logging.error("Failed to link jitterbuffer to depay")
            return False

        if not depay.link(h264parse):
            logging.error("Failed to link depay to h264parse")
            return False

        if not h264parse.link(decoder):
            logging.error("Failed to link h264parse to decoder")
            return False

        if not decoder.link(videoconvert):
            logging.error("Failed to link decoder to videoconvert")
            return False

        if not videoconvert.link(capsfilter):
            logging.error("Failed to link videoconvert to capsfilter")
            return False

        if not capsfilter.link(self.appsink):
            logging.error("Failed to link capsfilter to appsink")
            return False

        # Setup bus message handling
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self._on_error)
        bus.connect("message::eos", self._on_eos)
        bus.connect("message::state-changed", self._on_state_changed)

        return True

    def _on_new_sample(self, sink: GstApp.AppSink) -> Gst.FlowReturn:
        """Handle new sample from appsink."""
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.OK

        self.packet_count += 1
        self.last_frame_time = time.monotonic()

        buffer = sample.get_buffer()
        pts = buffer.pts

        # Check for old frames (before expensive operations)
        if self._should_drop_by_age(pts):
            self.dropped_old_frames += 1
            self.consecutive_old_frames += 1

            if self.consecutive_old_frames > self.max_consecutive_old_frames:
                logging.warning(
                    f"Dropped {self.consecutive_old_frames} consecutive old frames"
                )
                self.consecutive_old_frames = 0

            return Gst.FlowReturn.OK

        self.consecutive_old_frames = 0

        # Cache dimensions - only parse caps on first frame or resolution change
        if self._cached_width == 0:
            caps = sample.get_caps()
            structure = caps.get_structure(0)
            self._cached_width = structure.get_int("width")[1]
            self._cached_height = structure.get_int("height")[1]
            # Pre-allocate frame buffer
            self._frame_array = np.empty(
                (self._cached_height, self._cached_width, 3),
                dtype=np.uint8
            )

        success, mapinfo = buffer.map(Gst.MapFlags.READ)
        if not success:
            self.dropped_empty_frames += 1
            return Gst.FlowReturn.OK

        try:
            # Use frombuffer (faster than np.ndarray) + copy for frame_buffer
            frame = np.frombuffer(mapinfo.data, dtype=np.uint8).reshape(
                self._cached_height, self._cached_width, 3
            ).copy()
            self._update_frame(frame)

        finally:
            buffer.unmap(mapinfo)

        self._log_stats_if_needed()

        return Gst.FlowReturn.OK

    def _should_drop_by_age(self, pts: int) -> bool:
        """Check if frame should be dropped due to age."""
        if pts == Gst.CLOCK_TIME_NONE:
            return False

        if self.latest_pts is None:
            self.latest_pts = pts
            return False

        # PTS is in nanoseconds
        time_diff_seconds = (self.latest_pts - pts) / Gst.SECOND
        if time_diff_seconds >= self.max_age_seconds:
            return True

        if pts > self.latest_pts:
            self.latest_pts = pts

        return False

    def _check_timeout(self) -> bool:
        """Check if stream has timed out and clear frame if needed."""
        if self.last_frame_time == 0:
            return True

        elapsed = time.monotonic() - self.last_frame_time
        if elapsed > self.timeout_seconds:
            with self.frame_lock:
                if self.frame is not None or len(self.frame_buffer) > 0:
                    self.frame = None
                    self.frame_buffer.clear()
                    logging.info(
                        f"No frames received for {elapsed:.1f}s, clearing frame"
                    )

        return True

    def _on_error(self, bus: Gst.Bus, message: Gst.Message) -> None:
        """Handle pipeline error."""
        err, debug = message.parse_error()
        logging.error(f"GStreamer error: {err.message}")
        if debug:
            logging.debug(f"Debug info: {debug}")

        if self.loop and self.loop.is_running():
            self.loop.quit()

    def _on_eos(self, bus: Gst.Bus, message: Gst.Message) -> None:
        """Handle end of stream."""
        logging.info("End of stream received")
        if self.loop and self.loop.is_running():
            self.loop.quit()

    def _on_state_changed(self, bus: Gst.Bus, message: Gst.Message) -> None:
        """Handle state changes."""
        if message.src != self.pipeline:
            return

        old, new, pending = message.parse_state_changed()
        if new == Gst.State.PLAYING:
            logging.info("Pipeline is now PLAYING")

    def _main_loop(self) -> None:
        """Main receive/decode loop."""
        while self.running.is_set():
            if not self._build_pipeline():
                time.sleep(0.5)
                continue

            self.latest_pts = None
            self.consecutive_old_frames = 0
            self.last_frame_time = 0.0

            state = self.pipeline.set_state(Gst.State.PLAYING)
            if state == Gst.StateChangeReturn.FAILURE:
                logging.error("Failed to set pipeline to PLAYING")
                self._stop_pipeline()
                time.sleep(0.5)
                continue

            logging.info(f"GStreamer receiver started on port {self.port}")

            self.loop = GLib.MainLoop()

            def check_running() -> bool:
                if not self.running.is_set():
                    self.loop.quit()
                    return False

                self._check_timeout()
                return True

            GLib.timeout_add(100, check_running)

            try:
                self.loop.run()

            except Exception as e:
                logging.exception(f"Error in GStreamer main loop: {e}")

            finally:
                with self.frame_lock:
                    self.frame = None
                    self.frame_buffer.clear()

                self._stop_pipeline()
                self.keep_alive()

    def _stop_pipeline(self) -> None:
        """Stop and cleanup the pipeline."""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.appsink = None

        if self.loop and self.loop.is_running():
            self.loop.quit()

        self.loop = None

    def _cleanup(self) -> None:
        """Cleanup resources."""
        self._stop_pipeline()
