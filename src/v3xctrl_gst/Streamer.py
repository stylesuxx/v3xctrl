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

        # Default settings
        default_settings: Dict[str, Any] = {
            'width': 1280,
            'height': 720,
            'framerate': 30,
            'bitrate': 1800000,
            'buffertime': 150000000,
            'sizebuffers': 5,
            'recording_dir': '',
            'test_pattern': False,
            'i_frame_period': 30,
        }

        # Merge user settings with defaults
        self.settings: Dict[str, Any] = default_settings.copy()
        if settings:
            self.settings.update(settings)

        self.pipeline: Optional[Gst.Pipeline] = None
        self.loop: Optional[GLib.MainLoop] = None
        self.bus: Optional[Gst.Bus] = None

        # Constants
        self.BITRATE_MODE: int = 1
        self.BUFFERTIME_UDP: int = 150000000
        self.SIZEBUFFERS_UDP: int = 5
        self.H264_PROFILE: int = 0
        self.H264_LEVEL: int = 31
        self.SIZEBUFFERS_WRITE: int = 30

        # Initialize GStreamer
        Gst.init(None)

        self.control_server = ControlServer(self, control_socket)

    def _build_pipeline_string(self) -> str:
        """
        Build the GStreamer pipeline string based on settings.

        Returns:
            The complete pipeline string
        """
        # Build source branch
        if self.settings['test_pattern']:
            source_branch = (
                "videotestsrc is-live=true pattern=smpte name=src ! "
                "queue ! "
                "timeoverlay halignment=center valignment=center"
            )
        else:
            source_branch = "libcamerasrc name=camera"

        # Build tee branch for recording if needed
        tee_branch = ""
        if self.settings['recording_dir']:
            os.makedirs(self.settings['recording_dir'], exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            filename = f"{self.settings['recording_dir']}/stream-{timestamp}.ts"

            tee_branch = (
                f"t. ! queue leaky=downstream max-size-buffers={self.SIZEBUFFERS_WRITE} ! "
                f"h264parse ! mpegtsmux ! "
                f"filesink sync=false async=false location={filename}"
            )

        # Build the complete pipeline
        pipeline_str = (
            f"{source_branch} ! "
            f"video/x-raw,width={self.settings['width']},height={self.settings['height']},"
            f"framerate={self.settings['framerate']}/1,format=NV12,interlace-mode=progressive ! "
            f"queue max-size-buffers={self.settings['sizebuffers']} "
            f"max-size-time={self.settings['buffertime']} leaky=downstream ! "
            f"v4l2h264enc name=encoder extra-controls=\"controls,"
            f"repeat_sequence_header=1,"
            f"video_bitrate={self.settings['bitrate']},"
            f"bitrate_mode={self.BITRATE_MODE},"
            f"video_gop_size={self.settings['framerate']},"
            f"h264_i_frame_period={self.settings['i_frame_period']},"
            f"video_b_frames=0,"
            f"h264_profile={self.H264_PROFILE},"
            f"h264_level={self.H264_LEVEL}\" ! "
            f"video/x-h264,level=(string)4,profile=(string)high,stream-format=(string)byte-stream ! "
            f"tee name=t "
            f"t. ! queue max-size-buffers={self.SIZEBUFFERS_UDP} "
            f"max-size-time={self.BUFFERTIME_UDP} leaky=downstream ! "
            f"rtph264pay config-interval=1 pt=96 ! "
            f"udpsink name=sink host={self.host} port={self.port} "
            f"bind-port={self.bind_port} sync=false async=false"
        )

        if tee_branch:
            pipeline_str += f" {tee_branch}"

        return pipeline_str

    def _on_message(self, bus: Gst.Bus, message: Gst.Message) -> None:
        """
        Handle bus messages.

        Args:
            bus: GStreamer bus
            message: GStreamer message
        """
        t = message.type
        if t == Gst.MessageType.EOS:
            logging.info("End-of-stream")
            self.stop()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logging.error(f"Error: {err}, {debug}")
            self.stop()
        elif t == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            logging.warning(f"Warning: {warn}, {debug}")

    def start(self) -> None:
        """Create and start the pipeline."""
        pipeline_str = self._build_pipeline_string()
        logging.info(f"Launching pipeline:\n{pipeline_str}\n")

        # Create pipeline
        try:
            self.pipeline = Gst.parse_launch(pipeline_str)
        except GLib.Error as e:
            logging.error(f"Failed to create pipeline: {e}")
            sys.exit(1)

        # Set up bus
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self._on_message)

        # Set pipeline to playing
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
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

        # Create and run the main loop
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
