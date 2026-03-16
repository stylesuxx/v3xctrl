import os
import sys

# Holds os.add_dll_directory() handles — must stay alive for the lifetime of
# the process, or Windows removes those dirs from the DLL search path.
_dll_dir_handles = []

if getattr(sys, "frozen", False):
    bundle_dir = sys._MEIPASS

    # Tell PyGObject where to find GStreamer DLLs.
    # PyInstaller's --collect-all gi places transitive DLLs in one of:
    #   gstreamer_libs/bin/  (gstreamer-bundle pip package, Python name gstreamer_libs)
    #   gstreamer/bin/       (older gstreamer-bundle layout)
    # The bundle root (_MEIPASS) is always included first since some DLLs
    # (e.g. cairo-2.dll) are placed there by PyInstaller's binary analysis.
    dll_dirs = [bundle_dir]
    for gst_bin_candidate in [
        os.path.join(bundle_dir, "gstreamer_libs", "bin"),
        os.path.join(bundle_dir, "gstreamer", "bin"),
    ]:
        if os.path.isdir(gst_bin_candidate):
            dll_dirs.append(gst_bin_candidate)
            break

    # Also register any *_libs/bin directories for other gstreamer-bundle sub-packages
    for extra_bin in [
        os.path.join(bundle_dir, "gstreamer_plugins_libs", "bin"),
        os.path.join(bundle_dir, "gstreamer_plugins_restricted_libs", "bin"),
        os.path.join(bundle_dir, "gstreamer_plugins_gpl_libs", "bin"),
        os.path.join(bundle_dir, "gstreamer_plugins_gpl_restricted_libs", "bin"),
    ]:
        if os.path.isdir(extra_bin):
            dll_dirs.append(extra_bin)

    os.environ["PYGI_DLL_DIRS"] = os.pathsep.join(dll_dirs)

    # Python 3.8+ on Windows requires os.add_dll_directory() for the OS
    # loader to find dependent DLLs (PATH is no longer searched).
    # IMPORTANT: keep handles in a module-level list — if the return value is
    # garbage-collected, Windows removes that directory from the search path.
    if hasattr(os, "add_dll_directory"):
        for directory in dll_dirs:
            if os.path.isdir(directory):
                _dll_dir_handles.append(os.add_dll_directory(directory))

    # GStreamer plugin path - collect all non-empty plugin directories and join
    # them. gstreamer-bundle splits plugins across multiple Python packages
    # (gstreamer_libs, gstreamer_plugins_libs, gstreamer_plugins_restricted_libs)
    # each placing their plugin DLLs in their own lib/gstreamer-1.0/ subdir.
    _plugin_dir_candidates = [
        os.path.join(bundle_dir, "gstreamer_libs", "lib", "gstreamer-1.0"),
        os.path.join(bundle_dir, "gstreamer_plugins_libs", "lib", "gstreamer-1.0"),
        os.path.join(bundle_dir, "gstreamer_plugins_restricted_libs", "lib", "gstreamer-1.0"),
        os.path.join(bundle_dir, "gst_plugins"),
        os.path.join(bundle_dir, "gstreamer", "lib", "gstreamer-1.0"),
        os.path.join(bundle_dir, "gstreamer-1.0"),
    ]
    _plugin_dirs = [d for d in _plugin_dir_candidates if os.path.isdir(d) and os.listdir(d)]
    if _plugin_dirs:
        os.environ["GST_PLUGIN_PATH"] = os.pathsep.join(_plugin_dirs)

    # GIR typelib path - check known layouts:
    #   gi_typelibs/         (--collect-all gi flattens typelibs here)
    #   gstreamer_libs/lib/girepository-1.0/
    #   gstreamer/lib/girepository-1.0/
    #   girepository-1.0/
    for typelib_dir in [
        os.path.join(bundle_dir, "gi_typelibs"),
        os.path.join(bundle_dir, "gstreamer_libs", "lib", "girepository-1.0"),
        os.path.join(bundle_dir, "gstreamer", "lib", "girepository-1.0"),
        os.path.join(bundle_dir, "girepository-1.0"),
    ]:
        if os.path.isdir(typelib_dir):
            os.environ["GI_TYPELIB_PATH"] = typelib_dir
            break

    # Plugin registry cache - use user-local path to avoid writing to app bundle
    os.environ["GST_REGISTRY"] = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "v3xctrl",
        "gst-registry.bin",
    )

    # Prevent GStreamer from scanning system paths
    os.environ["GST_PLUGIN_SYSTEM_PATH"] = ""
