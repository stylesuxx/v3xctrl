import logging

logger = logging.getLogger(__name__)

# Holds os.add_dll_directory() handles for the process lifetime.
# On Windows, these keep the GStreamer DLL dirs registered in the OS loader
# search path so that plugin DLLs can find their dependencies (e.g. gstaudio).
# Module-level storage guarantees they are never GC'd while the module is live.
_dll_handles: list = []

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
            pkg_root = (
                os.path.dirname(gst_spec.origin)
                if gst_spec.origin is not None
                else (gst_spec.submodule_search_locations[0] if gst_spec.submodule_search_locations else None)
            )
            logger.debug("GStreamer check: gstreamer-bundle package '%s' found, root=%s", pkg, pkg_root)
            if pkg_root is not None:
                gst_bin = os.path.join(pkg_root, "bin")
                logger.debug("GStreamer check: expected DLL dir: %s (exists=%s)", gst_bin, os.path.isdir(gst_bin))
            break
    else:
        logger.debug("GStreamer check: gstreamer-bundle not found (tried gstreamer_libs, gstreamer)")
    if getattr(sys, "frozen", False):
        # PyInstaller's built-in gi hook (or gi/__init__.py itself) may set
        # GST_PLUGIN_PATH to include the bundle root (_MEIPASS), which causes
        # GStreamer to scan all DLLs there as plugins and corrupts the GLib
        # type system. Override it here, after all hooks have run, to point
        # only at the actual plugin directory.
        bundle_dir = sys._MEIPASS
        _plugin_dir_candidates = [
            os.path.join(bundle_dir, "gstreamer_libs", "lib", "gstreamer-1.0"),
            os.path.join(bundle_dir, "gstreamer_plugins", "lib", "gstreamer-1.0"),
            os.path.join(bundle_dir, "gstreamer_plugins_libs", "lib", "gstreamer-1.0"),
            os.path.join(bundle_dir, "gstreamer_plugins_restricted", "lib", "gstreamer-1.0"),
            os.path.join(bundle_dir, "gstreamer_plugins_gpl", "lib", "gstreamer-1.0"),
            os.path.join(bundle_dir, "gstreamer_plugins_gpl_restricted", "lib", "gstreamer-1.0"),
            os.path.join(bundle_dir, "gst_plugins"),
            os.path.join(bundle_dir, "gstreamer", "lib", "gstreamer-1.0"),
            os.path.join(bundle_dir, "gstreamer-1.0"),
        ]
        _plugin_dirs = [d for d in _plugin_dir_candidates if os.path.isdir(d) and os.listdir(d)]
        if _plugin_dirs:
            os.environ["GST_PLUGIN_PATH"] = os.pathsep.join(_plugin_dirs)
            os.environ["GST_PLUGIN_SYSTEM_PATH"] = ""

        logger.debug("GStreamer check: GST_PLUGIN_PATH=%s", os.environ.get("GST_PLUGIN_PATH", "(not set)"))
        logger.debug("GStreamer check: GI_TYPELIB_PATH=%s", os.environ.get("GI_TYPELIB_PATH", "(not set)"))

        # GLib uses LoadLibraryExW(..., LOAD_WITH_ALTERED_SEARCH_PATH) to load
        # plugin DLLs, which searches PATH but NOT os.add_dll_directory() dirs.
        # Prepend all DLL directories to PATH so plugin dependencies are found.
        # os.add_dll_directory() is also called for Python's own import machinery
        # (which uses LOAD_LIBRARY_SEARCH_DEFAULT_DIRS and ignores PATH).
        # Handles go into the module-level _dll_handles list so they are never GC'd.
        _dll_dir_candidates = [
            bundle_dir,
            os.path.join(bundle_dir, "gstreamer_libs", "bin"),
            os.path.join(bundle_dir, "gstreamer", "bin"),
            os.path.join(bundle_dir, "gstreamer_plugins_libs", "bin"),
            os.path.join(bundle_dir, "gstreamer_plugins_restricted_libs", "bin"),
            os.path.join(bundle_dir, "gstreamer_plugins_gpl_libs", "bin"),
            os.path.join(bundle_dir, "gstreamer_plugins_gpl_restricted_libs", "bin"),
        ]
        _existing_dirs = set(os.environ.get("PATH", "").split(os.pathsep))
        _new_dirs = [d for d in _dll_dir_candidates if os.path.isdir(d) and d not in _existing_dirs]
        if _new_dirs:
            os.environ["PATH"] = os.pathsep.join(_new_dirs) + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            for _d in _dll_dir_candidates:
                if os.path.isdir(_d):
                    _dll_handles.append(os.add_dll_directory(_d))
        logger.debug("GStreamer check: registered %d DLL dirs, PATH prepend: %s", len(_dll_handles), _new_dirs)

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
