import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

from v3xctrl_gst.ControlServer import ControlServer


class Streamer:
    def __init__(
        self,
        host: str,
        port: int,
        bind_port: int,
        settings: Optional[Dict[str, Any]] = None,
        control_socket: str = '/tmp/v3xctrl.sock'
    ) -> None:
        """
        Initialize the Streamer.

        Args:
            host: Destination host
            port: Destination port
            bind_port: Bind port
            settings: Optional configuration dictionary
            control_socket: Path to Unix socket file (default: /tmp/v3xctrl.sock)
        """
        self.host: str = host
        self.port: int = port
        self.bind_port: int = bind_port

        self.last_buffer_pts = None
        self.last_camera_pts = None
        self.frame_count = 0

        default_settings: Dict[str, Any] = {
            'width': 1280,
            'height': 720,
            'framerate': 30,
            'buffertime': 150000000,
            'sizebuffers': 5,
            'recording_dir': '',
            'test_pattern': False,
            'buffertime_udp': 150000000,
            'sizebuffers_udp': 5,
            'sizebuffers_write': 30,
            'mtu': 1400,
            'file_src': None,

            # Encoder (via CAPS)
            'h264_profile': "high",
            'h264_level': "4.1",
            'capture_io_mode':  4,

            # via extra-controls
            'bitrate_mode': 1,  # 0 VBR, 1: CBR
            'bitrate': 1800000,
            'h264_i_frame_period': 15,
            'h264_minimum_qp_value': 20,
            'h264_maximum_qp_value': 51,

            # Auto adjust
            'enable_i_frame_adjust': False,
            'max_i_frame_bytes': 51200,

            # Camera settings
            'af_mode': 0,
            'lens_position': 0,
        }

        self.settings: Dict[str, Any] = default_settings.copy()
        if settings:
            self.settings.update(settings)

        self.max_i_frame_bytes = self.settings['max_i_frame_bytes']

        self.qp_min_limit = self.settings['h264_minimum_qp_value']
        self.qp_max_limit = self.settings['h264_maximum_qp_value']
        self.current_qp_min = self.qp_min_limit

        lower_limit_percent = 0.85
        self.min_i_frame_bytes = self.max_i_frame_bytes * lower_limit_percent
        self.target_i_frame_bytes = (self.max_i_frame_bytes + self.min_i_frame_bytes) / 2

        # Fixed QP adjustment parameters
        self.qp_adjust_min_step = 1
        self.qp_adjust_max_step = 5
        self.qp_adjust_cooldown = 10
        self.frames_since_qp_adjust = 0

        self.pipeline: Optional[Gst.Pipeline] = None
        self.loop: Optional[GLib.MainLoop] = None
        self.bus: Optional[Gst.Bus] = None

        Gst.init(None)
        self.control_server = ControlServer(self, control_socket)

    def start(self) -> None:
        """Create and start the pipeline."""
        logging.info("Building pipeline...")

        if not self._build_pipeline():
            logging.error("Failed to build pipeline")
            sys.exit(1)

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self._on_message)

        state = self.pipeline.set_state(Gst.State.PLAYING)
        if state == Gst.StateChangeReturn.FAILURE:
            print("Unable to set the pipeline to the playing state.")
            sys.exit(1)

        logging.info("Pipeline running. Press Ctrl+C to stop.")

        self.control_server.start()

    def stop(self) -> None:
        """Stop the pipeline and quit the main loop."""
        if self.control_server:
            self.control_server.stop()

        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

        if self.loop:
            self.loop.quit()

    def run(self) -> None:
        """Start the pipeline and run the main loop."""
        self.start()

        self.loop = GLib.MainLoop()
        try:
            self.loop.run()

        except KeyboardInterrupt:
            logging.info("\nInterrupted by user")

        finally:
            self.stop()
            logging.info("Pipeline stopped.")

    def get_element(self, name: str) -> Optional[Gst.Element]:
        """
        Get a pipeline element by name for runtime control.

        Args:
            name: Element name

        Returns:
            GStreamer element or None if not found
        """
        if self.pipeline:
            return self.pipeline.get_by_name(name)

        return None

    def set_property(self, element_name: str, property_name: str, value: Any) -> bool:
        """
        Set a property on a named element.

        Args:
            element_name: Name of the element
            property_name: Name of the property
            value: Value to set

        Returns:
            True if successful, False otherwise
        """
        element = self.get_element(element_name)
        if element is None:
            logging.warn(f"Element '{element_name}' not found")
            return False

        try:
            element.set_property(property_name, value)
            return True

        except Exception as e:
            logging.error(f"Failed to set property '{property_name}' on element '{element_name}': {e}")
            return False

    def get_property(self, element_name: str, property_name: str) -> Optional[Any]:
        """
        Get a property value from a named element.

        Args:
            element_name: Name of the element
            property_name: Name of the property

        Returns:
            Property value or None if not found
        """
        element = self.get_element(element_name)
        if element is None:
            logging.error(f"Element '{element_name}' not found")
            return None

        try:
            return element.get_property(property_name)
        except Exception as e:
            logging.error(f"Failed to get property '{property_name}' from element '{element_name}': {e}")
            return None

    def update_properties(self, element_name: str, properties: Dict[str, Any]) -> bool:
        """
        Update multiple properties on a named element at once.

        Args:
            element_name: Name of the element
            properties: Dictionary of property names and values

        Returns:
            True if all properties were set successfully, False otherwise
        """
        element = self.get_element(element_name)
        if element is None:
            logging.error(f"Element '{element_name}' not found")
            return False

        success = True
        for prop_name, value in properties.items():
            try:
                element.set_property(prop_name, value)
            except Exception as e:
                logging.error(f"Failed to set property '{prop_name}' on element '{element_name}': {e}")
                success = False

        return success

    def list_properties(self, element_name: str) -> Optional[Dict[str, Any]]:
        """
        List all properties and their current values for a named element.

        Args:
            element_name: Name of the element

        Returns:
            Dictionary of property names and values, or None if element not found
        """
        element = self.get_element(element_name)
        if element is None:
            logging.error(f"Element '{element_name}' not found")
            return None

        properties = {}
        for prop in element.list_properties():
            try:
                prop_name = prop.name
                value = element.get_property(prop_name)
                properties[prop_name] = value
            except Exception:
                # Some properties might not be readable
                pass

        return properties

    def _on_message(self, bus: Gst.Bus, message: Gst.Message) -> None:
        """
        Handle bus messages.

        Args:
            bus: GStreamer bus
            message: GStreamer message
        """
        type = message.type
        if type == Gst.MessageType.EOS:
            logging.info("End-of-stream")
            self.stop()

        elif type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logging.error(f"Error: {err}, {debug}")
            self.stop()

        elif type == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            logging.warning(f"Warning: {warn}, {debug}")

    def _create_file_source(self) -> Optional[Gst.Bin]:
        """
        Create a bin containing file source, demuxer, and decoder with looping.

        Returns:
            Bin element with a src pad outputting raw video, or None on failure
        """
        bin_name = "file_source_bin"
        source_bin = Gst.Bin.new(bin_name)

        # Create elements for file source pipeline
        filesrc = Gst.ElementFactory.make("filesrc", "filesrc")
        if not filesrc:
            logging.error("Failed to create filesrc")
            return None

        filesrc.set_property("location", self.settings['file_src'])

        # QuickTime demuxer for .mov files
        demux = Gst.ElementFactory.make("qtdemux", "demux")
        if not demux:
            logging.error("Failed to create qtdemux")
            return None

        # H.264 parser
        h264parse = Gst.ElementFactory.make("h264parse", "h264parse")
        if not h264parse:
            logging.error("Failed to create h264parse")
            return None

        # Try software decoders in order of preference
        # Note: Cannot use v4l2h264dec since we need the hardware encoder for encoding later
        decoder_options = [
            ("avdec_h264", "avdec_h264 (FFmpeg)"),
            ("openh264dec", "openh264dec")
        ]

        decoder = None
        decoder_name = None
        for decoder_element, description in decoder_options:
            decoder = Gst.ElementFactory.make(decoder_element, "decoder")
            if decoder:
                decoder_name = description
                logging.info(f"Using H.264 decoder: {decoder_name}")
                break

        if not decoder:
            logging.error("Failed to create H.264 software decoder. Tried: " +
                         ", ".join([opt[0] for opt in decoder_options]))
            logging.error("You need to install: gstreamer1.0-libav (provides avdec_h264)")
            return None

        # Video converter to ensure proper format
        videoconvert = Gst.ElementFactory.make("videoconvert", "videoconvert")
        if not videoconvert:
            logging.error("Failed to create videoconvert")
            return None

        # Videorate for framerate conversion and timing enforcement
        videorate = Gst.ElementFactory.make("videorate", "videorate")
        if not videorate:
            logging.error("Failed to create videorate")
            return None

        # Configure videorate to enforce timing
        videorate.set_property("drop-only", False)
        videorate.set_property("skip-to-first", True)

        # Identity element to enforce real-time playback synchronization
        identity = Gst.ElementFactory.make("identity", "identity")
        if not identity:
            logging.error("Failed to create identity")
            return None

        identity.set_property("sync", True)

        # Add all elements to the bin
        source_bin.add(filesrc)
        source_bin.add(demux)
        source_bin.add(h264parse)
        source_bin.add(decoder)
        source_bin.add(videoconvert)
        source_bin.add(videorate)
        source_bin.add(identity)

        # Link static elements
        if not filesrc.link(demux):
            logging.error("Failed to link filesrc to demux")
            return None

        # Demux has dynamic pads, so we need to connect to the pad-added signal
        def on_demux_pad_added(element, pad):
            """Callback for when demuxer creates a pad"""
            pad_name = pad.get_name()
            logging.info(f"Demux pad added: {pad_name}")

            # We're looking for the video pad
            if pad_name.startswith("video_"):
                sink_pad = h264parse.get_static_pad("sink")
                if not sink_pad.is_linked():
                    ret = pad.link(sink_pad)
                    if ret != Gst.PadLinkReturn.OK:
                        logging.error(f"Failed to link demux to h264parse: {ret}")

        demux.connect("pad-added", on_demux_pad_added)

        # Link the rest of the chain
        if not h264parse.link(decoder):
            logging.error("Failed to link h264parse to decoder")
            return None

        if not decoder.link(videoconvert):
            logging.error("Failed to link decoder to videoconvert")
            return None

        if not videoconvert.link(videorate):
            logging.error("Failed to link videoconvert to videorate")
            return None

        if not videorate.link(identity):
            logging.error("Failed to link videorate to identity")
            return None

        # Create a ghost pad for the bin's output
        identity_src = identity.get_static_pad("src")
        ghost_pad = Gst.GhostPad.new("src", identity_src)
        source_bin.add_pad(ghost_pad)

        logging.info(f"Created file source from: {self.settings['file_src']}")
        return source_bin

    def _build_pipeline(self) -> bool:
        """
        Build the GStreamer pipeline programmatically.

        Returns:
            True if successful, False otherwise
        """
        self.pipeline = Gst.Pipeline.new("streamer-pipeline")

        overlay = None

        source = Gst.ElementFactory.make("libcamerasrc", "camera")
        if not source:
            logging.error("Failed to create libcamerasrc")
            return False

        source.set_property("af-mode", self.settings['af_mode'])
        source.set_property("lens-position", self.settings['lens_position'])

        # File Source if configured
        if self.settings['file_src']:
            source = self._create_file_source()
            if not source:
                logging.error("Failed to create file source pipeline")
                return False

        # Test Source if enabled
        elif self.settings['test_pattern']:
            source = Gst.ElementFactory.make("videotestsrc", "testsrc")
            if not source:
                logging.error("Failed to create videotestsrc")
                return False

            source.set_property("is-live", True)
            source.set_property("pattern", "smpte")

            overlay = Gst.ElementFactory.make("timeoverlay", "overlay")
            if not overlay:
                logging.error("Failed to create timeoverlay")
                return False

            overlay.set_property("halignment", "center")
            overlay.set_property("valignment", "center")

        # Create caps filter for video format
        input_caps_filter = Gst.ElementFactory.make("capsfilter", "input_caps")
        if not input_caps_filter:
            logging.error("Failed to create capsfilter")
            return False

        input_caps = Gst.Caps.from_string(
            f"video/x-raw,"
            f"width={self.settings['width']},"
            f"height={self.settings['height']},"
            f"framerate={self.settings['framerate']}/1,"
            f"format=NV12,"
            f"interlace-mode=progressive"
        )
        input_caps_filter.set_property("caps", input_caps)

        # Add probe to measure camera jitter
        camera_pad = input_caps_filter.get_static_pad("src")
        camera_pad.add_probe(Gst.PadProbeType.BUFFER, self._on_camera_buffer)

        queue_encoder = Gst.ElementFactory.make("queue", "queue_encoder")
        if not queue_encoder:
            logging.error("Failed to create encoder queue")
            return False

        queue_encoder.set_property("max-size-buffers", self.settings['sizebuffers'])
        queue_encoder.set_property("max-size-time", self.settings['buffertime'])
        queue_encoder.set_property("leaky", 2)  # Downstream leaky
        queue_encoder.connect("overrun", self._on_queue_overrun)

        encoder = Gst.ElementFactory.make("v4l2h264enc", "encoder")
        if not encoder:
            logging.error("Failed to create v4l2h264enc")
            return False

        encoder_controls = (
            f"controls,"
            f"video_b_frames=0,"
            f"repeat_sequence_header=1,"
            f"video_bitrate={self.settings['bitrate']},"
            f"bitrate_mode={self.settings['bitrate_mode']},"
            f"h264_i_frame_period={self.settings['h264_i_frame_period']},"
            f"h264_minimum_qp_value={self.settings['h264_minimum_qp_value']},"
            f"h264_maximum_qp_value={self.settings['h264_maximum_qp_value']}"
        )

        encoder.set_property("extra-controls", Gst.Structure.from_string(encoder_controls)[0])
        encoder.set_property("capture-io-mode", self.settings['capture_io_mode'])

        encoder_caps_filter = Gst.ElementFactory.make("capsfilter", "encoder_caps")
        if not encoder_caps_filter:
            logging.error("Failed to create encoder capsfilter")
            return False

        # Add probe to measure encoder jitter
        encoder_pad = encoder_caps_filter.get_static_pad("src")
        encoder_pad.add_probe(Gst.PadProbeType.BUFFER, self._on_encoder_buffer)

        encoder_caps = Gst.Caps.from_string(
            f"video/x-h264,"
            f"level=(string){self.settings['h264_level']},"
            f"profile=(string){self.settings['h264_profile']},"
            f"stream-format=(string)byte-stream"
        )
        encoder_caps_filter.set_property("caps", encoder_caps)

        tee = Gst.ElementFactory.make("tee", "t")
        if not tee:
            logging.error("Failed to create tee")
            return False

        queue_udp = Gst.ElementFactory.make("queue", "queue_udp")
        if not queue_udp:
            logging.error("Failed to create UDP queue")
            return False

        queue_udp.set_property("max-size-buffers", self.settings['sizebuffers_udp'])
        queue_udp.set_property("max-size-time", self.settings['buffertime_udp'])
        queue_udp.set_property("leaky", 2)  # Downstream
        queue_udp.connect("overrun", self._on_queue_overrun)

        payloader = Gst.ElementFactory.make("rtph264pay", "payloader")
        if not payloader:
            logging.error("Failed to create rtph264pay")
            return False

        payloader.set_property("config-interval", 1)
        payloader.set_property("pt", 96)
        payloader.set_property("mtu", self.settings['mtu'])

        udpsink = Gst.ElementFactory.make("udpsink", "udpsink")
        if not udpsink:
            logging.error("Failed to create udpsink")
            return False

        udpsink.set_property("host", self.host)
        udpsink.set_property("port", self.port)
        udpsink.set_property("bind-port", self.bind_port)

        # Enable sync for file sources to enforce real-time playback
        # Disable for live sources (camera/test) for minimum latency
        if self.settings['file_src']:
            udpsink.set_property("sync", True)
            udpsink.set_property("async", False)
        else:
            udpsink.set_property("sync", False)
            udpsink.set_property("async", False)

        # Add elements to pipeline
        self.pipeline.add(source)
        self.pipeline.add(input_caps_filter)
        self.pipeline.add(queue_encoder)
        self.pipeline.add(encoder)
        self.pipeline.add(encoder_caps_filter)
        self.pipeline.add(tee)
        self.pipeline.add(queue_udp)
        self.pipeline.add(payloader)
        self.pipeline.add(udpsink)

        # Link elements
        if overlay:
            self.pipeline.add(overlay)
            if not source.link(overlay):
                logging.error("Failed to link source to overlay")
                return False

            if not overlay.link(input_caps_filter):
                logging.error("Failed to link overlay to input_caps_filter")
                return False
        else:
            if not source.link(input_caps_filter):
                logging.error("Failed to link source to input_caps_filter")
                return False

        if not input_caps_filter.link(queue_encoder):
            logging.error("Failed to link input_caps_filter to queue_encoder")
            return False

        if not queue_encoder.link(encoder):
            logging.error("Failed to link queue_encoder to encoder")
            return False

        if not encoder.link(encoder_caps_filter):
            logging.error("Failed to link encoder to encoder_caps_filter")
            return False

        if not encoder_caps_filter.link(tee):
            logging.error("Failed to link encoder_caps_filter to tee")
            return False

        # Link UDP branch
        if not tee.link(queue_udp):
            logging.error("Failed to link tee to queue_udp")
            return False

        if not queue_udp.link(payloader):
            logging.error("Failed to link queue_udp to payloader")
            return False

        if not payloader.link(udpsink):
            logging.error("Failed to link payloader to udpsink")
            return False

        # Add recording branch if configured
        if self.settings['recording_dir']:
            if not self._add_recording_branch(tee):
                logging.warning("Failed to add recording branch")

        return True

    def _add_recording_branch(self, tee: Gst.Element) -> bool:
        """
        Add recording branch to the pipeline.

        Args:
            tee: Tee element to connect to

        Returns:
            True if successful, False otherwise
        """
        os.makedirs(self.settings['recording_dir'], exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        filename = f"{self.settings['recording_dir']}/stream-{timestamp}.ts"

        queue_rec = Gst.ElementFactory.make("queue", "queue_rec")
        if not queue_rec:
            logging.error("Failed to create recording queue")
            return False

        queue_rec.set_property("max-size-buffers", self.settings['sizebuffers_write'])
        queue_rec.set_property("leaky", 2)  # Downstream
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

        self.pipeline.add(queue_rec)
        self.pipeline.add(parser)
        self.pipeline.add(muxer)
        self.pipeline.add(filesink)

        if not tee.link(queue_rec):
            logging.error("Failed to link tee to queue_rec")
            return False

        if not queue_rec.link(parser):
            logging.error("Failed to link queue_rec to parser")
            return False

        if not parser.link(muxer):
            logging.error("Failed to link parser to muxer")
            return False

        if not muxer.link(filesink):
            logging.error("Failed to link muxer to filesink")
            return False

        logging.info(f"Recording to: {filename}")
        return True

    def _on_queue_overrun(self, element):
        logging.warning(f"Queue '{element.get_name()}' overrun - dropping frames!")

    def _on_encoder_buffer(self, pad, info):
        buffer = info.get_buffer()
        pts = buffer.pts

        is_keyframe = not buffer.has_flags(Gst.BufferFlags.DELTA_UNIT)
        if is_keyframe:
            size = buffer.get_size()
            logging.debug(f"i-frame: {size/1024:.1f} KB at PTS {pts/Gst.SECOND:.3f}s")

            # Adaptive QP adjustment based on I-frame size
            if self.settings['enable_i_frame_adjust']:
                if self.frames_since_qp_adjust >= self.qp_adjust_cooldown:
                    self._adjust_qp_based_on_i_frame_size(size)
                    self.frames_since_qp_adjust = 0

        if self.last_buffer_pts is not None:
            delta = (pts - self.last_buffer_pts) / Gst.SECOND
            expected = 1.0 / self.settings['framerate']
            jitter = abs(delta - expected) * 1000  # in ms

            if jitter > 5:
                logging.warning(f"Frame timing jitter: {jitter:.2f}ms (expected {expected*1000:.2f}ms, got {delta*1000:.2f}ms)")

        self.last_buffer_pts = pts
        self.frame_count += 1
        self.frames_since_qp_adjust += 1

        return Gst.PadProbeReturn.OK

    def _on_camera_buffer(self, pad, info):
        """Track camera frame timing"""
        buffer = info.get_buffer()
        pts = buffer.pts

        if self.last_camera_pts is not None:
            delta = (pts - self.last_camera_pts) / Gst.SECOND
            expected = 1.0 / self.settings['framerate']
            jitter = abs(delta - expected) * 1000

            if jitter > 5:
                logging.warning(f"CAMERA jitter: {jitter:.2f}ms (expected {expected*1000:.2f}ms, got {delta*1000:.2f}ms)")

        self.last_camera_pts = pts
        return Gst.PadProbeReturn.OK

    def _adjust_qp_based_on_i_frame_size(self, i_frame_size: int) -> None:
        """
        Adjust minimum QP based on I-frame size to control bandwidth spikes.
        Uses adaptive step size based on how far the I-frame is from target.

        Args:
            i_frame_size: Size of the I-frame in bytes
        """
        if (
            i_frame_size <= self.max_i_frame_bytes and
            i_frame_size >= self.min_i_frame_bytes
        ):
            # Within acceptable range, no adjustment
            return

        size_ratio = i_frame_size / self.target_i_frame_bytes

        # Calculate adaptive step size based on ratio
        calculated_step = int(size_ratio)
        step_size = min(max(calculated_step, self.qp_adjust_min_step), self.qp_adjust_max_step)

        new_qp_min = self.current_qp_min

        if i_frame_size > self.max_i_frame_bytes:
            # Increase min QP (more compression, lower quality)
            new_qp_min = min(self.current_qp_min + step_size, self.qp_max_limit)
            action = "increased"

        elif i_frame_size < self.min_i_frame_bytes:
            # Decrease min QP (less compression, better quality)
            new_qp_min = max(self.current_qp_min - step_size, self.qp_min_limit)
            action = "decreased"

        if new_qp_min != self.current_qp_min:
            self.current_qp_min = new_qp_min

            encoder = self.get_element("encoder")
            if encoder:
                try:
                    encoder_controls = (
                        f"controls,"
                        f"h264_minimum_qp_value={self.current_qp_min},"
                        f"h264_maximum_qp_value={self.settings['h264_maximum_qp_value']}"
                    )

                    encoder.set_property("extra-controls",
                        Gst.Structure.from_string(encoder_controls)[0])

                    logging.info(
                        f"QP min {action} by {step_size} to {self.current_qp_min} "
                        f"(I-frame: {i_frame_size / 1024:.1f}KB, "
                        f"target: {self.target_i_frame_bytes / 1024:.1f}KB, "
                        f"range: {self.min_i_frame_bytes / 1024:.1f}-{self.max_i_frame_bytes / 1024:.1f}KB, "
                        f"ratio: {size_ratio:.2f})"
                    )

                except Exception as e:
                    logging.error(f"Failed to adjust QP: {e}")
