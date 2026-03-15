import os
import sys

if getattr(sys, "frozen", False):
    bundle_dir = sys._MEIPASS

    # GStreamer plugin path - check both layouts:
    # 1. gstreamer-bundle pip wheel layout (plugins inside gstreamer package)
    # 2. Manual MSYS2 bundle layout (gstreamer-1.0/ directory)
    for plugin_dir in [
        os.path.join(bundle_dir, "gstreamer", "lib", "gstreamer-1.0"),
        os.path.join(bundle_dir, "gstreamer-1.0"),
    ]:
        if os.path.isdir(plugin_dir):
            os.environ["GST_PLUGIN_PATH"] = plugin_dir
            break

    # GIR typelib path
    for typelib_dir in [
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
