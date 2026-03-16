import logging

logger = logging.getLogger(__name__)

# Required GStreamer elements for H264 RTP reception
_REQUIRED_GST_ELEMENTS = [
    "udpsrc",  # gst-plugins-good
    "rtpjitterbuffer",  # gst-plugins-good
    "rtph264depay",  # gst-plugins-good
    "h264parse",  # gst-plugins-bad
    "avdec_h264",  # gst-libav
    "videoconvert",  # gst-plugins-base
    "appsink",  # gst-plugins-base
]

_gstreamer_available = False
_gstreamer_check_done = False


def _check_gstreamer_elements() -> str | None:
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
    import importlib.util
    import os
    import sys

    logger.debug("GStreamer check: Python executable: %s", sys.executable)
    logger.debug("GStreamer check: frozen=%s", getattr(sys, "frozen", False))
    if getattr(sys, "frozen", False):
        logger.debug("GStreamer check: _MEIPASS=%s", getattr(sys, "_MEIPASS", "n/a"))

    gi_spec = importlib.util.find_spec("gi")
    if gi_spec is not None:
        logger.debug("GStreamer check: gi found at %s", gi_spec.origin)
    else:
        logger.debug("GStreamer check: gi module not found on sys.path")

    for pkg in ("gstreamer_libs", "gstreamer"):
        gst_spec = importlib.util.find_spec(pkg)
        if gst_spec is not None:
            logger.debug("GStreamer check: gstreamer-bundle package '%s' found at %s", pkg, gst_spec.origin)
            gst_bin = os.path.join(os.path.dirname(gst_spec.origin), "bin")
            logger.debug("GStreamer check: expected DLL dir: %s (exists=%s)", gst_bin, os.path.isdir(gst_bin))
            break
    else:
        logger.debug("GStreamer check: gstreamer-bundle not found (tried gstreamer_libs, gstreamer)")
    if getattr(sys, "frozen", False):
        logger.debug("GStreamer check: GST_PLUGIN_PATH=%s", os.environ.get("GST_PLUGIN_PATH", "(not set)"))
        logger.debug("GStreamer check: GI_TYPELIB_PATH=%s", os.environ.get("GI_TYPELIB_PATH", "(not set)"))

    try:
        import gi

        gi.require_version("Gst", "1.0")
        gi.require_version("GstApp", "1.0")
        from gi.repository import Gst

        Gst.init(None)

        missing = _check_gstreamer_elements()
        if missing:
            logger.info(f"GStreamer receiver not available: missing '{missing}' element")
            return False

        logger.debug("GStreamer check: all elements present, GStreamer is available")
        return True

    except ImportError as e:
        logger.info(f"GStreamer receiver not available: {e}")
        return False

    except Exception as e:
        logger.warning(f"GStreamer initialization failed: {e}")
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
