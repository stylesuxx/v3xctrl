import os
import sys

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

    # Also register gstreamer_plugins_libs/bin/ — contains FFmpeg DLLs needed by gstlibav
    for extra_bin in [
        os.path.join(bundle_dir, "gstreamer_plugins_libs", "bin"),
    ]:
        if os.path.isdir(extra_bin):
            dll_dirs.append(extra_bin)

    os.environ["PYGI_DLL_DIRS"] = os.pathsep.join(dll_dirs)

    # GLib uses LoadLibraryExW(..., LOAD_WITH_ALTERED_SEARCH_PATH) to load
    # plugin DLLs.  That flag is mutually exclusive with
    # LOAD_LIBRARY_SEARCH_USER_DIRS, so os.add_dll_directory() has no effect
    # on GStreamer plugin loading.  The LOAD_WITH_ALTERED_SEARCH_PATH search
    # order falls back to PATH, so prepending the DLL dirs to PATH is the
    # correct fix for GLib/GStreamer.
    #
    # os.add_dll_directory() is kept as well because Python 3.8+ uses
    # LOAD_LIBRARY_SEARCH_DEFAULT_DIRS for its own import machinery (which
    # honours AddDllDirectory but ignores PATH), so it is still needed when
    # gi._gi.pyd and other extension modules are imported.
    existing_path = os.environ.get("PATH", "")
    new_path_entries = [d for d in dll_dirs if os.path.isdir(d)]
    os.environ["PATH"] = os.pathsep.join(new_path_entries) + (os.pathsep + existing_path if existing_path else "")

    if hasattr(os, "add_dll_directory"):
        if not hasattr(sys, "_pyi_gst_dll_handles"):
            sys._pyi_gst_dll_handles = []
        for directory in dll_dirs:
            if os.path.isdir(directory):
                sys._pyi_gst_dll_handles.append(os.add_dll_directory(directory))

    # GStreamer plugin path — only the two packages containing required plugins.
    # gstreamer_plugins_libs/lib/gstreamer-1.0/ (gstges, gstnle) is intentionally
    # excluded: those plugins are bundled for their bin/ FFmpeg DLLs only.
    _plugin_dir_candidates = [
        os.path.join(bundle_dir, "gstreamer_libs", "lib", "gstreamer-1.0"),
        os.path.join(bundle_dir, "gstreamer_plugins", "lib", "gstreamer-1.0"),
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
