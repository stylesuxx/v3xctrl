import contextlib
import logging
import os
import signal
import sys
import time
from threading import Event
from typing import Any

import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # noqa: E402

from v3xctrl_gst.ControlServer import ControlServer  # noqa: E402
from v3xctrl_gst.PipelineTimer import PipelineTimer  # noqa: E402
from v3xctrl_gst.QPManager import QPManager  # noqa: E402
from v3xctrl_gst.RecordingManager import RecordingManager  # noqa: E402
from v3xctrl_gst.SEIInjector import SEIInjector  # noqa: E402
from v3xctrl_gst.SourceRegistry import SourceRegistry  # noqa: E402
from v3xctrl_helper import NTPClock  # noqa: E402

logger = logging.getLogger(__name__)


class Streamer:
    def __init__(
        self,
        host: str,
        port: int,
        bind_port: int,
        settings: dict[str, Any] | None = None,
        control_socket: str = "/tmp/v3xctrl.sock",
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

        self.last_udp_overflow_time: float = 0

        self._udpsink_network_down: bool = False
        self._udpsink_recovery_timeout_id: int | None = None

        self._udp_queue_overrun_active: bool = False
        self._udp_queue_overrun_recovery_timeout_id: int | None = None

        self.timer = PipelineTimer()

        default_settings: dict[str, Any] = {
            "width": 1280,
            "height": 720,
            "framerate": 30,
            "buffertime": 50000000,
            "sizebuffers": 2,
            "recording_dir": None,
            "recording": False,
            "test_pattern": False,
            "buffertime_udp": 50000000,
            "sizebuffers_udp": 2,
            "sizebuffers_write": 30,
            "mtu": 1400,
            "file_src": None,
            # Encoder (via CAPS)
            "h264_profile": "high",
            "h264_level": "4.1",
            "capture_io_mode": 4,
            "output_io_mode": 4,
            # via extra-controls
            "bitrate_mode": 1,  # 0 VBR, 1: CBR
            "bitrate": 1800000,
            "h264_i_frame_period": 15,
            "h264_minimum_qp_value": 20,
            "h264_maximum_qp_value": 51,
            # Auto adjust
            "enable_i_frame_adjust": False,
            "max_i_frame_bytes": 25600,
            # Camera settings
            "af_mode": 0,
            "lens_position": 0,
            "analogue_gain_mode": 0,
            "analogue_gain": 1,
            "exposure_time_mode": 0,
            "exposure_time": 32000,
            "brightness": 0.0,
            "contrast": 1.0,
            "saturation": 1.0,
            "sharpness": 0.0,
            # Sensor mode control
            "sensor_mode_width": 0,
            "sensor_mode_height": 0,
            # Pipeline timing
            "timing_enabled": False,
        }

        self.settings: dict[str, Any] = default_settings.copy()
        if settings:
            self.settings.update(settings)

        if self.settings["timing_enabled"]:
            self.timer.enable()

        logger.debug(self.settings)

        self.pipeline: Gst.Pipeline | None = None
        self.loop: GLib.MainLoop | None = None
        self.bus: Gst.Bus | None = None

        Gst.init(None)

        self.ntp_clock: NTPClock | None = None
        self.sei_injector: SEIInjector | None = None
        if self.timer.enabled:
            self.ntp_clock = NTPClock()
            self.sei_injector = SEIInjector(self.ntp_clock)

        self.control_server = ControlServer(self, control_socket)

    def start(self) -> None:
        """Create and start the pipeline."""
        logger.info("Building pipeline...")

        if not self._build_pipeline():
            logger.error("Failed to build pipeline")
            sys.exit(1)

        self.recording_manager = RecordingManager(
            pipeline=self.pipeline,
            tee=self.get_element("t"),
            recording_dir=self.settings["recording_dir"],
            sizebuffers=self.settings["sizebuffers_write"],
            on_queue_overrun=self._on_queue_overrun,
        )

        self.qp_manager = QPManager(
            encoder=self.get_element("encoder"),
            max_i_frame_bytes=self.settings["max_i_frame_bytes"],
            qp_min=self.settings["h264_minimum_qp_value"],
            qp_max=self.settings["h264_maximum_qp_value"],
        )

        assert self.pipeline is not None
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self._on_message)

        state = self.pipeline.set_state(Gst.State.PLAYING)
        if state == Gst.StateChangeReturn.FAILURE:
            logger.error("Unable to set the pipeline to the playing state.")
            sys.exit(1)

        if self.settings["recording"] and self.settings["recording_dir"]:
            if self.start_recording():
                logger.info("Auto-started recording on pipeline start")
            else:
                logger.warning("Failed to auto-start recording")

        self.control_server.start()

    # Timeout for pipeline NULL transition before forcing exit.
    # If the v4l2 encoder hangs during shutdown, we bail before the encoder
    # thread enters uninterruptible kernel sleep (D-state).
    SHUTDOWN_TIMEOUT_NS: int = 3 * 1_000_000_000  # 3 seconds in nanoseconds

    def stop(self) -> None:
        """Stop the pipeline and quit the main loop."""
        if self.recording_manager.is_recording:
            self.recording_manager.stop()

        if self.control_server:
            self.control_server.stop()

        if self.ntp_clock:
            self.ntp_clock.stop()

        if self.pipeline:
            self.pipeline.send_event(Gst.Event.new_eos())
            self.pipeline.set_state(Gst.State.NULL)

            result = self.pipeline.get_state(self.SHUTDOWN_TIMEOUT_NS)

            if result[0] == Gst.StateChangeReturn.FAILURE or result[1] != Gst.State.NULL:
                logger.error("Pipeline failed to reach NULL state within timeout - forcing exit")
                os._exit(1)

        if self.loop:
            self.loop.quit()

    def run(self) -> None:
        """Start the pipeline and run the main loop."""
        self.start()

        self.loop = GLib.MainLoop()

        # Handle SIGTERM (sent by systemd on service stop) so we can
        # shut down the pipeline gracefully instead of being killed.
        # Use Python's signal module directly - GLib.unix_signal_add requires
        # the main loop to dispatch, but Python's default SIGTERM handler
        # terminates the process before GLib can process the pipe event.
        signal.signal(signal.SIGTERM, self._on_sigterm)

        try:
            self.loop.run()

        except KeyboardInterrupt:
            logger.info("\nInterrupted by user")

        finally:
            self.stop()
            logger.info("Pipeline stopped.")

    def _on_sigterm(self, _signum: int, _frame: Any) -> None:
        if self.loop:
            self.loop.quit()

    def get_element(self, name: str) -> Gst.Element | None:
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

    def set_property(self, element_name: str, property_name: str, value: Any, max_retries: int = 3) -> bool:
        """
        Set a property on a named element. Will validate the result and attempt
        to set multiple times

        Args:
            element_name: Name of the element
            property_name: Name of the property
            value: Value to set
            max_retries: Retry in case the setting did not stick

        Returns:
            True if successful, False otherwise
        """
        for attempt in range(max_retries):
            result = {"success": False}
            event = Event()

            def _do_set(result=result, event=event):
                element = self.get_element(element_name)
                if element:
                    try:
                        element.set_property(property_name, value)
                        result["success"] = True
                    except Exception as e:
                        logger.error(f"Failed to set property '{property_name}': {e}")
                event.set()
                return False

            GLib.idle_add(_do_set)
            event.wait(timeout=0.5)

            if not result["success"]:
                return False

            # Give the element some time to process the setting - especially
            # important for elements that interact with hardware like libcamera
            time.sleep(0.5)

            # Verify setting actually stuck
            verify_result = {"actual": None}
            verify_event = Event()

            def _do_verify(verify_result=verify_result, verify_event=verify_event):
                element = self.get_element(element_name)
                if element:
                    with contextlib.suppress(Exception):
                        verify_result["actual"] = element.get_property(property_name)
                verify_event.set()
                return False

            GLib.idle_add(_do_verify)
            verify_event.wait(timeout=0.5)

            # For float properties, use approximate comparison
            if isinstance(verify_result["actual"], float):
                if abs(verify_result["actual"] - value) < 0.001:
                    if attempt > 0:
                        logger.debug(f"Property '{property_name}' stuck after {attempt + 1} attempts")
                    return True

            elif verify_result["actual"] == value:
                if attempt > 0:
                    logger.debug(f"Property '{property_name}' stuck after {attempt + 1} attempts")
                return True

            if attempt < max_retries - 1:
                logger.debug(
                    f"Attempt {attempt + 1}: value is {verify_result['actual']}, expected {value}, retrying..."
                )

        logger.warning(
            f"Property '{property_name}' failed to stick after {max_retries} attempts (value: {verify_result['actual']})"
        )
        return False

    def get_property(self, element_name: str, property_name: str) -> Any | None:
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
            logger.error(f"Element '{element_name}' not found")
            return None

        try:
            return element.get_property(property_name)
        except Exception as e:
            logger.error(f"Failed to get property '{property_name}' from element '{element_name}': {e}")
            return None

    def list_properties(self, element_name: str) -> dict[str, Any] | None:
        """
        List all properties and their current values for a named element.

        Args:
            element_name: Name of the element

        Returns:
            Dictionary of property names and values, or None if element not found
        """
        element = self.get_element(element_name)
        if element is None:
            logger.error(f"Element '{element_name}' not found")
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

    def get_stats(self) -> dict[str, Any]:
        return {
            "recording": self.recording_manager.is_recording,
            "qp_min": self.qp_manager.current_qp_min,
            "qp_max": self.qp_manager.qp_max,
            "udp_overrun": (time.monotonic() - self.last_udp_overflow_time) < 5,
        }

    def enable_timing(self, enabled: bool = True) -> None:
        if enabled:
            self.timer.enable()
        else:
            self.timer.disable()

    def start_recording(self) -> bool:
        return self.recording_manager.start()

    def stop_recording(self) -> bool:
        return self.recording_manager.stop()

    def _on_message(self, bus: Gst.Bus, message: Gst.Message) -> None:
        """
        Handle bus messages.

        Args:
            bus: GStreamer bus
            message: GStreamer message
        """
        type = message.type
        if type == Gst.MessageType.EOS:
            logger.info("End-of-stream")
            self.stop()

        elif type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Error: {err}, {debug}")
            self.stop()

        elif type == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            if self._is_udpsink_warning(message):
                self._handle_network_unreachable()
            else:
                logger.warning(f"Warning: {warn}, {debug}")

    @staticmethod
    def _is_udpsink_warning(message: Gst.Message) -> bool:
        return message.src is not None and message.src.get_name() == "udpsink"

    def _handle_network_unreachable(self) -> None:
        if not self._udpsink_network_down:
            logger.warning("Network is unreachable")
            self._udpsink_network_down = True

        self._reschedule_recovery_timeout()

    def _reschedule_recovery_timeout(self) -> None:
        if self._udpsink_recovery_timeout_id is not None:
            GLib.source_remove(self._udpsink_recovery_timeout_id)

        self._udpsink_recovery_timeout_id = GLib.timeout_add(1000, self._on_recovery_timeout)

    def _on_recovery_timeout(self) -> bool:
        self._udpsink_network_down = False
        self._udpsink_recovery_timeout_id = None
        logger.info("Network recovered")

        return False

    def _build_pipeline(self) -> bool:
        """
        Build the GStreamer pipeline programmatically.

        Returns:
            True if successful, False otherwise
        """
        self.pipeline = Gst.Pipeline.new("streamer-pipeline")

        source_type = "camera"
        if self.settings.get("file_src"):
            source_type = "file"
        elif self.settings.get("test_pattern"):
            source_type = "test"

        # Create source using registry
        try:
            source_builder = SourceRegistry.create(source_type, self.settings)
            _ = source_builder.build(self.pipeline)
            source_output = source_builder.get_output_element()
        except (RuntimeError, ValueError) as e:
            logger.error(f"Failed to create source: {e}")
            return False

        # Create caps filter for video format
        input_caps_filter = Gst.ElementFactory.make("capsfilter", "input_caps")
        if not input_caps_filter:
            logger.error("Failed to create capsfilter")
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
        self.pipeline.add(input_caps_filter)

        # Add probe on source output to measure camera/ISP latency
        if self.timer.enabled:
            source_pad = source_output.get_static_pad("src")
            source_pad.add_probe(Gst.PadProbeType.BUFFER, self._on_source_buffer)

        # Add probe to measure camera jitter
        camera_pad = input_caps_filter.get_static_pad("src")
        camera_pad.add_probe(Gst.PadProbeType.BUFFER, self._on_camera_buffer)

        # Link source output to encoder pipeline
        if not source_output.link(input_caps_filter):
            logger.error("Failed to link source to input_caps_filter")
            return False

        queue_encoder = Gst.ElementFactory.make("queue", "queue_encoder")
        if not queue_encoder:
            logger.error("Failed to create encoder queue")
            return False

        queue_encoder.set_property("max-size-buffers", self.settings["sizebuffers"])
        queue_encoder.set_property("max-size-time", self.settings["buffertime"])
        queue_encoder.set_property("leaky", 2)  # Downstream leaky
        queue_encoder.connect("overrun", self._on_queue_overrun)
        self.pipeline.add(queue_encoder)

        encoder = Gst.ElementFactory.make("v4l2h264enc", "encoder")
        if not encoder:
            logger.error("Failed to create v4l2h264enc")
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
        encoder.set_property("capture-io-mode", self.settings["capture_io_mode"])
        encoder.set_property("output-io-mode", self.settings["output_io_mode"])
        self.pipeline.add(encoder)

        if self.timer.enabled and self.sei_injector:
            encoder_sink_pad = encoder.get_static_pad("sink")
            encoder_sink_pad.add_probe(Gst.PadProbeType.BUFFER, self.sei_injector.on_pre_encode)

        encoder_caps_filter = Gst.ElementFactory.make("capsfilter", "encoder_caps")
        if not encoder_caps_filter:
            logger.error("Failed to create encoder capsfilter")
            return False

        # Add probe to measure encoder jitter
        encoder_pad = encoder_caps_filter.get_static_pad("src")
        encoder_pad.add_probe(Gst.PadProbeType.BUFFER, self._on_encoder_buffer)

        if self.timer.enabled and self.sei_injector:
            encoder_pad.add_probe(Gst.PadProbeType.BUFFER, self.sei_injector.on_post_encode)

        encoder_caps = Gst.Caps.from_string(
            f"video/x-h264,"
            f"level=(string){self.settings['h264_level']},"
            f"profile=(string){self.settings['h264_profile']},"
            f"stream-format=(string)byte-stream"
        )
        encoder_caps_filter.set_property("caps", encoder_caps)
        self.pipeline.add(encoder_caps_filter)

        tee = Gst.ElementFactory.make("tee", "t")
        if not tee:
            logger.error("Failed to create tee")
            return False
        self.pipeline.add(tee)

        queue_udp = Gst.ElementFactory.make("queue", "queue_udp")
        if not queue_udp:
            logger.error("Failed to create UDP queue")
            return False

        queue_udp.set_property("max-size-buffers", self.settings["sizebuffers_udp"])
        queue_udp.set_property("max-size-time", self.settings["buffertime_udp"])
        queue_udp.set_property("leaky", 2)  # Downstream
        queue_udp.connect("overrun", self._on_udp_queue_overrun)
        self.pipeline.add(queue_udp)

        payloader = Gst.ElementFactory.make("rtph264pay", "payloader")
        if not payloader:
            logger.error("Failed to create rtph264pay")
            return False

        payloader.set_property("aggregate-mode", 1)  # zero-latency
        payloader.set_property("config-interval", 1)
        payloader.set_property("pt", 96)
        payloader.set_property("mtu", self.settings["mtu"])
        self.pipeline.add(payloader)

        # Add probe to measure total pipeline latency (before UDP send)
        # Use sink pad: rtph264pay uses gst_pad_push_list() on src,
        # which is not caught by BUFFER probes.
        if self.timer.enabled:
            payloader_pad = payloader.get_static_pad("sink")
            payloader_pad.add_probe(Gst.PadProbeType.BUFFER, self._on_payloader_in)

        udpsink = Gst.ElementFactory.make("udpsink", "udpsink")
        if not udpsink:
            logger.error("Failed to create udpsink")
            return False

        if self.timer.enabled:
            udpsink_pad = udpsink.get_static_pad("sink")
            udpsink_pad.add_probe(Gst.PadProbeType.BUFFER_LIST, self._on_udpsink_buffer_list)

        udpsink.set_property("host", self.host)
        udpsink.set_property("port", self.port)
        udpsink.set_property("bind-port", self.bind_port)

        # Use source builder's NEEDS_SYNC property
        udpsink.set_property("sync", source_builder.NEEDS_SYNC)
        udpsink.set_property("async", False)
        self.pipeline.add(udpsink)

        # Link encoder pipeline
        if not input_caps_filter.link(queue_encoder):
            logger.error("Failed to link input_caps_filter to queue_encoder")
            return False

        if not queue_encoder.link(encoder):
            logger.error("Failed to link queue_encoder to encoder")
            return False

        if not encoder.link(encoder_caps_filter):
            logger.error("Failed to link encoder to encoder_caps_filter")
            return False

        if not encoder_caps_filter.link(tee):
            logger.error("Failed to link encoder_caps_filter to tee")
            return False

        # Link UDP branch
        if not tee.link(queue_udp):
            logger.error("Failed to link tee to queue_udp")
            return False

        if not queue_udp.link(payloader):
            logger.error("Failed to link queue_udp to payloader")
            return False

        if not payloader.link(udpsink):
            logger.error("Failed to link payloader to udpsink")
            return False

        return True

    def _on_queue_overrun(self, element):
        logger.warning(f"Queue '{element.get_name()}' overrun - dropping frames!")

    def _on_udp_queue_overrun(self, _):
        """
        UDP queue overrun means frames can not be pushed out fast enough -
        this is a limitation of the network.
        """
        self.last_udp_overflow_time = time.monotonic()

        if not self._udp_queue_overrun_active:
            logger.error("UDP queue overrun - dropping frames!")
            self._udp_queue_overrun_active = True

        self._reschedule_udp_queue_overrun_recovery_timeout()

    def _reschedule_udp_queue_overrun_recovery_timeout(self) -> None:
        if self._udp_queue_overrun_recovery_timeout_id is not None:
            GLib.source_remove(self._udp_queue_overrun_recovery_timeout_id)

        self._udp_queue_overrun_recovery_timeout_id = GLib.timeout_add(
            1000, self._on_udp_queue_overrun_recovery_timeout
        )

    def _on_udp_queue_overrun_recovery_timeout(self) -> bool:
        self._udp_queue_overrun_active = False
        self._udp_queue_overrun_recovery_timeout_id = None
        logger.info("UDP queue recovered")

        return False

    def _on_encoder_buffer(self, pad, info):
        buffer = info.get_buffer()
        pts = buffer.pts

        is_keyframe = not buffer.has_flags(Gst.BufferFlags.DELTA_UNIT)

        if is_keyframe and self.settings["enable_i_frame_adjust"]:
            size = buffer.get_size()
            logger.debug(f"i-frame: {size / 1024:.1f} KB at PTS {pts / Gst.SECOND:.3f}s")
            self.qp_manager.on_keyframe(size)

        if self.last_buffer_pts is not None:
            delta = (pts - self.last_buffer_pts) / Gst.SECOND
            expected = 1.0 / self.settings["framerate"]
            jitter = abs(delta - expected) * 1000  # in ms

            if jitter > 5:
                logger.warning(
                    f"Frame timing jitter: {jitter:.2f}ms (expected {expected * 1000:.2f}ms, got {delta * 1000:.2f}ms)"
                )

        self.last_buffer_pts = pts
        self.frame_count += 1

        self.timer.on_encoder_buffer(pts)

        return Gst.PadProbeReturn.OK

    def _on_source_buffer(self, pad, info):
        buffer = info.get_buffer()
        self.timer.on_source_buffer(buffer.pts, self.pipeline)

        return Gst.PadProbeReturn.OK

    def _on_camera_buffer(self, pad, info):
        buffer = info.get_buffer()
        pts = buffer.pts

        if self.last_camera_pts is not None:
            delta = (pts - self.last_camera_pts) / Gst.SECOND
            expected = 1.0 / self.settings["framerate"]
            jitter = abs(delta - expected) * 1000

            if jitter > 5:
                logger.warning(
                    f"CAMERA jitter: {jitter:.2f}ms (expected {expected * 1000:.2f}ms, got {delta * 1000:.2f}ms)"
                )

        self.last_camera_pts = pts

        self.timer.on_capsfilter_buffer(pts)

        return Gst.PadProbeReturn.OK

    def _on_payloader_in(self, pad, info):
        buffer = info.get_buffer()
        self.timer.on_payloader_in(buffer.pts)
        return Gst.PadProbeReturn.OK

    def _on_udpsink_buffer_list(self, pad, info):
        buffer_list = info.get_buffer_list()
        if buffer_list.length() == 0:
            return Gst.PadProbeReturn.OK
        self.timer.on_udpsink_buffer_list(buffer_list.get(0).pts)
        return Gst.PadProbeReturn.OK
