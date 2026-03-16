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

    os.environ["PYGI_DLL_DIRS"] = os.pathsep.join(dll_dirs)

    # Python 3.8+ on Windows requires os.add_dll_directory() for the OS
    # loader to find dependent DLLs (PATH is no longer searched).
    if hasattr(os, "add_dll_directory"):
        for directory in dll_dirs:
            if os.path.isdir(directory):
                os.add_dll_directory(directory)

    # GStreamer plugin path - check known layouts produced by PyInstaller:
    #   gst_plugins/         (--collect-all gi flattens plugins here)
    #   gstreamer_libs/lib/gstreamer-1.0/  (gstreamer-bundle internal layout)
    #   gstreamer/lib/gstreamer-1.0/       (older layout)
    #   gstreamer-1.0/                     (manual MSYS2 bundle layout)
    for plugin_dir in [
        os.path.join(bundle_dir, "gst_plugins"),
        os.path.join(bundle_dir, "gstreamer_libs", "lib", "gstreamer-1.0"),
        os.path.join(bundle_dir, "gstreamer", "lib", "gstreamer-1.0"),
        os.path.join(bundle_dir, "gstreamer-1.0"),
    ]:
        if os.path.isdir(plugin_dir):
            os.environ["GST_PLUGIN_PATH"] = plugin_dir
            break

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
