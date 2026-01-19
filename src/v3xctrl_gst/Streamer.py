import logging
import sys
from threading import Event
import time
from typing import Optional, Dict, Any

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

from v3xctrl_gst.SourceRegistry import SourceRegistry
from v3xctrl_gst.ControlServer import ControlServer
from v3xctrl_gst.RecordingManager import RecordingManager
from v3xctrl_gst.QPManager import QPManager


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
            'recording_dir': None,
            'recording': False,
            'test_pattern': False,
            'buffertime_udp': 150000000,
            'sizebuffers_udp': 5,
            'sizebuffers_write': 30,
            'mtu': 1400,
            'file_src': None,

            # Encoder (via CAPS)
            'h264_profile': "high",
            'h264_level': "4.1",
            'capture_io_mode': 4,

            # via extra-controls
            'bitrate_mode': 1,  # 0 VBR, 1: CBR
            'bitrate': 1800000,
            'h264_i_frame_period': 15,
            'h264_minimum_qp_value': 20,
            'h264_maximum_qp_value': 51,

            # Auto adjust
            'enable_i_frame_adjust': False,
            'max_i_frame_bytes': 25600,

            # Camera settings
            'af_mode': 0,
            'lens_position': 0,
            'analogue_gain_mode': 0,
            'analogue_gain': 1,
            'exposure_time_mode': 0,
            'exposure_time': 32000,

            'brightness': 0.0,
            'contrast': 1.0,
            'saturation': 1.0,
            'sharpness': 0.0,

            # Sensor mode control
            'sensor_mode_width': 0,
            'sensor_mode_height': 0,
        }

        self.settings: Dict[str, Any] = default_settings.copy()
        if settings:
            self.settings.update(settings)

        logging.debug(self.settings)

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

        self.recording_manager = RecordingManager(
            pipeline=self.pipeline,
            tee=self.get_element("t"),
            recording_dir=self.settings['recording_dir'],
            sizebuffers=self.settings['sizebuffers_write'],
            on_queue_overrun=self._on_queue_overrun
        )

        self.qp_manager = QPManager(
            encoder=self.get_element("encoder"),
            max_i_frame_bytes=self.settings['max_i_frame_bytes'],
            qp_min=self.settings['h264_minimum_qp_value'],
            qp_max=self.settings['h264_maximum_qp_value'],
        )

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self._on_message)

        state = self.pipeline.set_state(Gst.State.PLAYING)
        if state == Gst.StateChangeReturn.FAILURE:
            print("Unable to set the pipeline to the playing state.")
            sys.exit(1)

        logging.info("Pipeline running. Press Ctrl+C to stop.")

        if self.settings['recording'] and self.settings['recording_dir']:
            if self.start_recording():
                logging.info("Auto-started recording on pipeline start")
            else:
                logging.warning("Failed to auto-start recording")

        self.control_server.start()

    def stop(self) -> None:
        """Stop the pipeline and quit the main loop."""
        if self.recording_manager.is_recording:
            self.recording_manager.stop()

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
            result = {'success': False}
            event = Event()

            def _do_set():
                element = self.get_element(element_name)
                if element:
                    try:
                        element.set_property(property_name, value)
                        result['success'] = True
                    except Exception as e:
                        logging.error(f"Failed to set property '{property_name}': {e}")
                event.set()
                return False

            GLib.idle_add(_do_set)
            event.wait(timeout=0.5)

            if not result['success']:
                return False

            # Give the element some time to process the setting - especially
            # important for elements that interact with hardware like libcamera
            time.sleep(0.5)

            # Verify setting actually stuck
            verify_result = {'actual': None}
            verify_event = Event()

            def _do_verify():
                element = self.get_element(element_name)
                if element:
                    try:
                        verify_result['actual'] = element.get_property(property_name)
                    except Exception:
                        pass
                verify_event.set()
                return False

            GLib.idle_add(_do_verify)
            verify_event.wait(timeout=0.5)

            # For float properties, use approximate comparison
            if isinstance(verify_result['actual'], float):
                if abs(verify_result['actual'] - value) < 0.001:
                    if attempt > 0:
                        logging.debug(f"Property '{property_name}' stuck after {attempt + 1} attempts")
                    return True

            elif verify_result['actual'] == value:
                if attempt > 0:
                    logging.debug(f"Property '{property_name}' stuck after {attempt + 1} attempts")
                return True

            if attempt < max_retries - 1:
                logging.debug(f"Attempt {attempt + 1}: value is {verify_result['actual']}, expected {value}, retrying...")

        logging.warning(f"Property '{property_name}' failed to stick after {max_retries} attempts (value: {verify_result['actual']})")
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

    def get_stats(self) -> Dict[str, Any]:
        return {
            'recording': self.recording_manager.is_recording,
            'qp_min': self.qp_manager.current_qp_min,
            'qp_max': self.qp_manager.qp_max,
        }

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
            logging.info("End-of-stream")
            self.stop()

        elif type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logging.error(f"Error: {err}, {debug}")
            self.stop()

        elif type == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            logging.warning(f"Warning: {warn}, {debug}")

    def _build_pipeline(self) -> bool:
        """
        Build the GStreamer pipeline programmatically.

        Returns:
            True if successful, False otherwise
        """
        self.pipeline = Gst.Pipeline.new("streamer-pipeline")

        source_type = 'camera'
        if self.settings.get('file_src'):
            source_type = 'file'
        elif self.settings.get('test_pattern'):
            source_type = 'test'

        # Create source using registry
        try:
            source_builder = SourceRegistry.create(source_type, self.settings)
            _ = source_builder.build(self.pipeline)
            source_output = source_builder.get_output_element()
        except (RuntimeError, ValueError) as e:
            logging.error(f"Failed to create source: {e}")
            return False

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
        self.pipeline.add(input_caps_filter)

        # Add probe to measure camera jitter
        camera_pad = input_caps_filter.get_static_pad("src")
        camera_pad.add_probe(Gst.PadProbeType.BUFFER, self._on_camera_buffer)

        # Link source output to encoder pipeline
        if not source_output.link(input_caps_filter):
            logging.error("Failed to link source to input_caps_filter")
            return False

        queue_encoder = Gst.ElementFactory.make("queue", "queue_encoder")
        if not queue_encoder:
            logging.error("Failed to create encoder queue")
            return False

        queue_encoder.set_property("max-size-buffers", self.settings['sizebuffers'])
        queue_encoder.set_property("max-size-time", self.settings['buffertime'])
        queue_encoder.set_property("leaky", 2)  # Downstream leaky
        queue_encoder.connect("overrun", self._on_queue_overrun)
        self.pipeline.add(queue_encoder)

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
        self.pipeline.add(encoder)

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
        self.pipeline.add(encoder_caps_filter)

        tee = Gst.ElementFactory.make("tee", "t")
        if not tee:
            logging.error("Failed to create tee")
            return False
        self.pipeline.add(tee)

        queue_udp = Gst.ElementFactory.make("queue", "queue_udp")
        if not queue_udp:
            logging.error("Failed to create UDP queue")
            return False

        queue_udp.set_property("max-size-buffers", self.settings['sizebuffers_udp'])
        queue_udp.set_property("max-size-time", self.settings['buffertime_udp'])
        queue_udp.set_property("leaky", 2)  # Downstream
        queue_udp.connect("overrun", self._on_queue_overrun)
        self.pipeline.add(queue_udp)

        payloader = Gst.ElementFactory.make("rtph264pay", "payloader")
        if not payloader:
            logging.error("Failed to create rtph264pay")
            return False

        payloader.set_property("config-interval", 1)
        payloader.set_property("pt", 96)
        payloader.set_property("mtu", self.settings['mtu'])
        self.pipeline.add(payloader)

        udpsink = Gst.ElementFactory.make("udpsink", "udpsink")
        if not udpsink:
            logging.error("Failed to create udpsink")
            return False

        udpsink.set_property("host", self.host)
        udpsink.set_property("port", self.port)
        udpsink.set_property("bind-port", self.bind_port)

        # Use source builder's NEEDS_SYNC property
        udpsink.set_property("sync", source_builder.NEEDS_SYNC)
        udpsink.set_property("async", False)
        self.pipeline.add(udpsink)

        # Link encoder pipeline
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

        return True

    def _on_queue_overrun(self, element):
        logging.warning(f"Queue '{element.get_name()}' overrun - dropping frames!")

    def _on_encoder_buffer(self, pad, info):
        buffer = info.get_buffer()
        pts = buffer.pts

        is_keyframe = not buffer.has_flags(Gst.BufferFlags.DELTA_UNIT)

        if is_keyframe and self.settings['enable_i_frame_adjust']:
            size = buffer.get_size()
            logging.debug(f"i-frame: {size/1024:.1f} KB at PTS {pts/Gst.SECOND:.3f}s")
            self.qp_manager.on_keyframe(size)

        if self.last_buffer_pts is not None:
            delta = (pts - self.last_buffer_pts) / Gst.SECOND
            expected = 1.0 / self.settings['framerate']
            jitter = abs(delta - expected) * 1000  # in ms

            if jitter > 5:
                logging.warning(f"Frame timing jitter: {jitter:.2f}ms (expected {expected*1000:.2f}ms, got {delta*1000:.2f}ms)")

        self.last_buffer_pts = pts
        self.frame_count += 1

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
