import logging
from typing import Optional

# Required GStreamer elements for H264 RTP reception
_REQUIRED_GST_ELEMENTS = [
    "udpsrc",           # gst-plugins-good
    "rtpjitterbuffer",  # gst-plugins-good
    "rtph264depay",     # gst-plugins-good
    "h264parse",        # gst-plugins-bad
    "avdec_h264",       # gst-libav
    "videoconvert",     # gst-plugins-base
    "appsink",          # gst-plugins-base
]

_gstreamer_available = False
_gstreamer_check_done = False


def _check_gstreamer_elements() -> Optional[str]:
    """Check if required GStreamer elements are available.

    Returns:
        None if all elements available, or name of first missing element.
    """
    from gi.repository import Gst
    for element in _REQUIRED_GST_ELEMENTS:
        if not Gst.ElementFactory.find(element):
            return element

    return None


def _do_gstreamer_check() -> bool:
    try:
        import gi
        gi.require_version('Gst', '1.0')
        gi.require_version('GstApp', '1.0')
        from gi.repository import Gst
        Gst.init(None)

        missing = _check_gstreamer_elements()
        if missing:
            logging.info(f"GStreamer receiver not available: missing '{missing}' element")
            return False

        return True

    except ImportError as e:
        logging.info(f"GStreamer receiver not available: {e}")
        return False

    except Exception as e:
        logging.warning(f"GStreamer initialization failed: {e}")
        return False


def is_gstreamer_available() -> bool:
    """Check if GStreamer receiver is available.

    This performs a lazy check on first call, caching the result.
    Checks for:
    - PyGObject (gi) module
    - GStreamer initialization
    - Required GStreamer elements (udpsrc, rtph264depay, avdec_h264, etc.)
    """
    global _gstreamer_available, _gstreamer_check_done

    if not _gstreamer_check_done:
        _gstreamer_available = _do_gstreamer_check()
        _gstreamer_check_done = True

    return _gstreamer_available
