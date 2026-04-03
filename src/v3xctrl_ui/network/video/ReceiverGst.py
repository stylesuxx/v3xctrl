import logging
import time
from collections.abc import Callable

import gi
import numpy as np

from v3xctrl_helper import parse_sei_nal
from v3xctrl_ui.network.video.ClockOffset import ClockOffset
from v3xctrl_ui.network.video.Receiver import Receiver

gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import GLib, Gst, GstApp  # noqa: E402

logger = logging.getLogger(__name__)


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
        super().__init__(port, keep_alive, log_interval, history_size, max_frame_age_ms, render_ratio)

        Gst.init(None)

        self.pipeline: Gst.Pipeline | None = None
        self.appsink: GstApp.AppSink | None = None
        self.loop: GLib.MainLoop | None = None

        self.latest_pts: int | None = None
        self.consecutive_old_frames = 0
        self.max_consecutive_old_frames = 60

        self.last_frame_time: float = 0.0

        # Pipeline timing via pad probes (only used when timing_enabled)
        # Track first packet arrival per PTS (for receive timing)
        self._receive_start_times: dict[int, float] | None = None
        # Track decoder entry time per PTS (for decode timing)
        self._decode_start_times: dict[int, float] | None = None
        # Store calculated receive durations to pass through pipeline
        self._receive_durations: dict[int, float] | None = None
        # Collect receive timing samples for logging
        self._timing_receive_samples: list[float] | None = None

        # SEI-based end-to-end latency (only used when timing_enabled)
        self._clock_offset: ClockOffset | None = None
        self._sei_timestamps: dict[int, int] | None = None
        self._timing_e2e_samples: list[float] | None = None

        # Cached frame dimensions and pre-allocated buffer
        self._cached_width: int = 0
        self._cached_height: int = 0
        self._frame_array: np.ndarray | None = None

    def set_clock_offset(self, clock_offset: ClockOffset) -> None:
        self._clock_offset = clock_offset

    def _on_frame_displayed(self, capture_timestamp_us: int) -> None:
        if capture_timestamp_us > 0 and self._clock_offset is not None and self._clock_offset.valid:
            viewer_us = int(time.time() * 1_000_000)
            e2e_us = viewer_us - capture_timestamp_us + self._clock_offset.offset_us
            if e2e_us >= 0:
                self._timing_e2e_samples.append(e2e_us / 1_000_000)

    def _setup(self) -> None:
        """Setup GStreamer pipeline."""
        pass

    def _on_receive_probe(self, pad: Gst.Pad, info: Gst.PadProbeInfo) -> Gst.PadProbeReturn:
        """Record timestamp when FIRST packet of each frame arrives."""
        buffer = info.get_buffer()
        if buffer and buffer.pts != Gst.CLOCK_TIME_NONE:
            pts = buffer.pts
            # Only record first packet for each PTS (frame)
            if pts not in self._receive_start_times:
                self._receive_start_times[pts] = time.monotonic()
        return Gst.PadProbeReturn.OK

    def _on_decoder_entry_probe(self, pad: Gst.Pad, info: Gst.PadProbeInfo) -> Gst.PadProbeReturn:
        """Record when complete frame enters decoder, calculate receive time."""
        buffer = info.get_buffer()
        if buffer and buffer.pts != Gst.CLOCK_TIME_NONE:
            pts = buffer.pts
            now = time.monotonic()

            # Calculate receive duration (first packet -> decoder entry)
            receive_start = self._receive_start_times.pop(pts, None)
            if receive_start is not None:
                self._receive_durations[pts] = now - receive_start

            # Record decoder entry time for decode duration
            self._decode_start_times[pts] = now
        return Gst.PadProbeReturn.OK

    def _on_sei_extract_probe(self, pad: Gst.Pad, info: Gst.PadProbeInfo) -> Gst.PadProbeReturn:
        """Extract SEI timestamp from H.264 data after depayloading."""
        buffer = info.get_buffer()
        if buffer and buffer.pts != Gst.CLOCK_TIME_NONE:
            ok, map_info = buffer.map(Gst.MapFlags.READ)
            if ok:
                data = bytes(map_info.data)
                buffer.unmap(map_info)
                result = parse_sei_nal(data)
                if result is not None:
                    # Cap dict size to prevent leaks from dropped frames
                    if len(self._sei_timestamps) > 300:
                        self._sei_timestamps.clear()
                    self._sei_timestamps[buffer.pts] = result
        return Gst.PadProbeReturn.OK

    def _build_pipeline(self) -> bool:
        """Build and configure the GStreamer pipeline dynamically."""
        self.pipeline = Gst.Pipeline.new("receiver-pipeline")
        if not self.pipeline:
            logger.error("Failed to create pipeline")
            return False

        # UDP source
        udpsrc = Gst.ElementFactory.make("udpsrc", "udpsrc")
        if not udpsrc:
            logger.error("Failed to create udpsrc")
            return False

        udpsrc.set_property("port", self.port)
        caps = Gst.Caps.from_string("application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000")
        udpsrc.set_property("caps", caps)

        # RTP jitter buffer
        jitterbuffer = Gst.ElementFactory.make("rtpjitterbuffer", "jitterbuffer")
        if not jitterbuffer:
            logger.error("Failed to create rtpjitterbuffer")
            return False

        jitterbuffer.set_property("latency", 0)
        jitterbuffer.set_property("drop-on-latency", True)

        # RTP H264 depayloader
        depay = Gst.ElementFactory.make("rtph264depay", "depay")
        if not depay:
            logger.error("Failed to create rtph264depay")
            return False

        # H264 parser
        h264parse = Gst.ElementFactory.make("h264parse", "h264parse")
        if not h264parse:
            logger.error("Failed to create h264parse")
            return False

        # H264 decoder
        decoder = Gst.ElementFactory.make("avdec_h264", "decoder")
        if not decoder:
            logger.error("Failed to create avdec_h264")
            return False

        decoder.set_property("output-corrupt", False)
        decoder.set_property("max-threads", 2)

        # Video converter
        videoconvert = Gst.ElementFactory.make("videoconvert", "videoconvert")
        if not videoconvert:
            logger.error("Failed to create videoconvert")
            return False

        # Caps filter for RGB output
        capsfilter = Gst.ElementFactory.make("capsfilter", "capsfilter")
        if not capsfilter:
            logger.error("Failed to create capsfilter")
            return False

        rgb_caps = Gst.Caps.from_string("video/x-raw,format=RGB")
        capsfilter.set_property("caps", rgb_caps)

        # App sink
        self.appsink = Gst.ElementFactory.make("appsink", "sink")
        if not self.appsink:
            logger.error("Failed to create appsink")
            return False

        self.appsink.set_property("emit-signals", True)
        self.appsink.set_property("max-buffers", 1)
        self.appsink.set_property("drop", True)
        self.appsink.set_property("sync", False)
        self.appsink.connect("new-sample", self._on_new_sample)

        # Add elements to pipeline
        elements = [udpsrc, jitterbuffer, depay, h264parse, decoder, videoconvert, capsfilter, self.appsink]

        for element in elements:
            self.pipeline.add(element)

        # Link elements
        if not udpsrc.link(jitterbuffer):
            logger.error("Failed to link udpsrc to jitterbuffer")
            return False

        if not jitterbuffer.link(depay):
            logger.error("Failed to link jitterbuffer to depay")
            return False

        if not depay.link(h264parse):
            logger.error("Failed to link depay to h264parse")
            return False

        if not h264parse.link(decoder):
            logger.error("Failed to link h264parse to decoder")
            return False

        if not decoder.link(videoconvert):
            logger.error("Failed to link decoder to videoconvert")
            return False

        if not videoconvert.link(capsfilter):
            logger.error("Failed to link videoconvert to capsfilter")
            return False

        if not capsfilter.link(self.appsink):
            logger.error("Failed to link capsfilter to appsink")
            return False

        # Add pipeline timing probes when timing is enabled
        if self.timing_enabled:
            self._receive_start_times = {}
            self._decode_start_times = {}
            self._receive_durations = {}
            self._timing_receive_samples = []

            # Probe at jitterbuffer input - first packet arrival
            jitter_sink = jitterbuffer.get_static_pad("sink")
            if jitter_sink:
                jitter_sink.add_probe(Gst.PadProbeType.BUFFER, self._on_receive_probe)

            # Probe at decoder input - complete frame ready for decode
            decoder_sink = decoder.get_static_pad("sink")
            if decoder_sink:
                decoder_sink.add_probe(Gst.PadProbeType.BUFFER, self._on_decoder_entry_probe)

            # SEI extraction for e2e latency (probe depay output = Annex B)
            self._sei_timestamps = {}
            self._timing_e2e_samples = []

            depay_src = depay.get_static_pad("src")
            if depay_src:
                depay_src.add_probe(Gst.PadProbeType.BUFFER, self._on_sei_extract_probe)

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

            if self._sei_timestamps is not None:
                self._sei_timestamps.pop(pts, None)

            if self.consecutive_old_frames > self.max_consecutive_old_frames:
                logger.warning(f"Dropped {self.consecutive_old_frames} consecutive old frames")
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
            self._frame_array = np.empty((self._cached_height, self._cached_width, 3), dtype=np.uint8)

        success, mapinfo = buffer.map(Gst.MapFlags.READ)
        if not success:
            self.dropped_empty_frames += 1
            return Gst.FlowReturn.OK

        try:
            # Use frombuffer (faster than np.ndarray) + copy for frame_buffer
            frame = (
                np.frombuffer(mapinfo.data, dtype=np.uint8).reshape(self._cached_height, self._cached_width, 3).copy()
            )

            # Calculate timing if enabled
            decode_duration = 0.0
            capture_timestamp_us = 0
            if self.timing_enabled and self._decode_start_times is not None:
                # Get decode duration (decoder entry -> appsink)
                decode_start = self._decode_start_times.pop(pts, None)
                if decode_start is not None:
                    decode_duration = time.monotonic() - decode_start

                # Collect receive duration sample for logging
                receive_duration = self._receive_durations.pop(pts, None)
                if receive_duration is not None:
                    self._timing_receive_samples.append(receive_duration)

                # Pass SEI capture timestamp through to display time
                if self._sei_timestamps is not None:
                    capture_timestamp_us = self._sei_timestamps.pop(pts, None) or 0

            self._update_frame(frame, decode_duration, capture_timestamp_us)

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
                    logger.info(f"No frames received for {elapsed:.1f}s, clearing frame")

        return True

    def _on_error(self, bus: Gst.Bus, message: Gst.Message) -> None:
        """Handle pipeline error."""
        err, debug = message.parse_error()
        logger.error(f"GStreamer error: {err.message}")
        if debug:
            logger.debug(f"Debug info: {debug}")

        if self.loop and self.loop.is_running():
            self.loop.quit()

    def _on_eos(self, bus: Gst.Bus, message: Gst.Message) -> None:
        """Handle end of stream."""
        logger.info("End of stream received")
        if self.loop and self.loop.is_running():
            self.loop.quit()

    def _on_state_changed(self, bus: Gst.Bus, message: Gst.Message) -> None:
        """Handle state changes."""
        if message.src != self.pipeline:
            return

        _old, new, _pending = message.parse_state_changed()
        if new == Gst.State.PLAYING:
            logger.info("Pipeline is now PLAYING")

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
                logger.error("Failed to set pipeline to PLAYING")
                self._stop_pipeline()
                time.sleep(0.5)
                continue

            logger.info(f"GStreamer receiver started on port {self.port}")

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
                logger.exception(f"Error in GStreamer main loop: {e}")

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

        # Clear timing data
        if self._receive_start_times is not None:
            self._receive_start_times.clear()
        if self._decode_start_times is not None:
            self._decode_start_times.clear()
        if self._receive_durations is not None:
            self._receive_durations.clear()
        if self._timing_receive_samples is not None:
            self._timing_receive_samples.clear()
        if self._sei_timestamps is not None:
            self._sei_timestamps.clear()
        if self._timing_e2e_samples is not None:
            self._timing_e2e_samples.clear()

    def _log_timing_stats(self) -> None:
        """Override to include receive timing and e2e latency in GST receiver."""
        if not self.timing_buffer_samples:
            return

        def stats(samples: list) -> tuple[float, float, float]:
            if not samples:
                return 0.0, 0.0, 0.0
            return min(samples), sum(samples) / len(samples), max(samples)

        decode_samples = list(self.timing_decode_samples)
        buffer_samples = list(self.timing_buffer_samples)
        receive_samples = list(self._timing_receive_samples) if self._timing_receive_samples else []
        e2e_samples = list(self._timing_e2e_samples) if self._timing_e2e_samples else []

        _rec_min, rec_avg, _rec_max = stats(receive_samples)
        _dec_min, dec_avg, _dec_max = stats(decode_samples)
        buf_min, buf_avg, buf_max = stats(buffer_samples)
        e2e_min, e2e_avg, e2e_max = stats(e2e_samples)

        def fmt(label: str, mn: float, avg: float, mx: float) -> str:
            return f"{label}: {avg * 1000:.1f}ms ({mn * 1000:.1f}-{mx * 1000:.1f})"

        total_avg_ms = (rec_avg + dec_avg + buf_avg) * 1000

        parts = [
            fmt("receive", _rec_min, rec_avg, _rec_max),
            fmt("decode", _dec_min, dec_avg, _dec_max),
            fmt("buffer", buf_min, buf_avg, buf_max),
            f"total: {total_avg_ms:.1f}ms",
        ]

        if e2e_samples:
            parts.append(fmt("e2e", e2e_min, e2e_avg, e2e_max))

        if self._clock_offset is not None and self._clock_offset.valid:
            offset_ms = self._clock_offset.offset_us / 1000
            parts.append(f"clock-offset: {offset_ms:.1f}ms")

        logger.debug(f"[TIMING] {' | '.join(parts)}")

        self.timing_decode_samples.clear()
        self.timing_buffer_samples.clear()
        if self._timing_receive_samples:
            self._timing_receive_samples.clear()
        if self._timing_e2e_samples:
            self._timing_e2e_samples.clear()

    def _cleanup(self) -> None:
        """Cleanup resources."""
        self._stop_pipeline()
