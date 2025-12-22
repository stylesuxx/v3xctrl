import logging

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

from v3xctrl_gst.Sources.SourceBuilder import SourceBuilder


class CameraSourceBuilder(SourceBuilder):
    """Builds libcamerasrc with optional sensor mode control"""

    NEEDS_SYNC = False  # Live source, no sync needed

    def build(self, pipeline: Gst.Pipeline) -> Gst.Element:
        """
        Build libcamerasrc and optionally configure dual-stream sensor mode.

        Args:
            pipeline: GStreamer pipeline to add elements to

        Returns:
            The libcamerasrc element
        """
        source = Gst.ElementFactory.make("libcamerasrc", "camera")
        if not source:
            raise RuntimeError("Failed to create libcamerasrc")

        source.set_property("af-mode", self.settings['af_mode'])
        source.set_property("lens-position", self.settings['lens_position'])

        source.set_property("brightness", self.settings['brightness'])
        source.set_property("contrast", self.settings['contrast'])
        source.set_property("saturation", self.settings['saturation'])
        source.set_property("sharpness", self.settings['sharpness'])

        if (
            self.settings['analogue_gain_mode'] == 1 or
            self.settings['exposure_time_mode'] == 1
        ):
            # Disable auto exposure if gain or exposure are set to manual
            source.set_property("ae-enable", 0)

            source.set_property("analogue-gain-mode", self.settings['analogue_gain_mode'])
            source.set_property("analogue-gain", self.settings['analogue_gain'])

            source.set_property("exposure-time-mode", self.settings['exposure_time_mode'])
            source.set_property("exposure-time", self.settings['exposure_time'])

        # Add source to pipeline FIRST (before requesting pads)
        pipeline.add(source)

        # Check if sensor mode control is requested
        sensor_width = self.settings.get('sensor_mode_width', 0)
        sensor_height = self.settings.get('sensor_mode_height', 0)

        if sensor_width > 0 and sensor_height > 0:
            # Force specific sensor mode
            self._setup_sensor_mode(pipeline, source, sensor_width, sensor_height)
            self._output_element = pipeline.get_by_name("queue_camera")
        else:
            self._output_element = source

        return source

    def _setup_sensor_mode(
        self,
        pipeline: Gst.Pipeline,
        source: Gst.Element,
        width: int,
        height: int
    ) -> None:
        """
        Setup dual-stream sensor mode control.

        Creates a raw stream with specified dimensions to force the camera
        into a specific sensor mode, while the main stream is used for encoding.

        Args:
            pipeline: GStreamer pipeline
            source: libcamerasrc element
            width: Sensor mode width
            height: Sensor mode height
        """
        logging.info(f"Enabling sensor mode control: {width}x{height}")

        # Get pads - main pad is STATIC, raw pad is REQUEST
        main_pad = source.get_static_pad("src")
        raw_pad = source.get_request_pad("src_%u")

        if not main_pad or not raw_pad:
            raise RuntimeError(
                f"Failed to get camera pads (main_pad={main_pad}, raw_pad={raw_pad})"
            )

        queue_camera = Gst.ElementFactory.make("queue", "queue_camera")
        if not queue_camera:
            raise RuntimeError("Failed to create camera queue")

        queue_camera.set_property("max-size-buffers", 0)
        queue_camera.set_property("max-size-time", 0)
        queue_camera.set_property("max-size-bytes", 0)
        pipeline.add(queue_camera)

        # Create raw stream elements
        queue_raw = Gst.ElementFactory.make("queue", "queue_raw")
        raw_caps_filter = Gst.ElementFactory.make("capsfilter", "raw_caps_filter")
        fakesink_raw = Gst.ElementFactory.make("fakesink", "fakesink_raw")

        if not all([queue_raw, raw_caps_filter, fakesink_raw]):
            raise RuntimeError("Could not create raw stream elements")

        # Configure raw stream - caps will force sensor mode
        raw_caps_str = f"video/x-raw,width={width},height={height}"
        raw_caps = Gst.Caps.from_string(raw_caps_str)
        raw_caps_filter.set_property("caps", raw_caps)

        queue_raw.set_property("max-size-buffers", 0)
        queue_raw.set_property("max-size-time", 0)
        queue_raw.set_property("max-size-bytes", 0)

        fakesink_raw.set_property("sync", False)
        fakesink_raw.set_property("async", False)

        pipeline.add(queue_raw)
        pipeline.add(raw_caps_filter)
        pipeline.add(fakesink_raw)

        queue_camera_sink = queue_camera.get_static_pad("sink")
        queue_raw_sink = queue_raw.get_static_pad("sink")

        if main_pad.link(queue_camera_sink) != Gst.PadLinkReturn.OK:
            raise RuntimeError("Failed to link main_pad to queue_camera")

        if raw_pad.link(queue_raw_sink) != Gst.PadLinkReturn.OK:
            raise RuntimeError("Failed to link raw_pad to queue_raw")

        if not queue_raw.link(raw_caps_filter):
            raise RuntimeError("Failed to link queue_raw to raw_caps_filter")

        if not raw_caps_filter.link(fakesink_raw):
            raise RuntimeError("Failed to link raw_caps_filter to fakesink_raw")

        logging.info("Configured raw stream for sensor mode control")
