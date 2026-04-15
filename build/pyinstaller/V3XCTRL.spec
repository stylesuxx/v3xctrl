# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# SPECPATH is the directory containing this spec file (build/pyinstaller/).
# Resolve source root relative to spec file so this works regardless of CWD.
SRC = os.path.normpath(os.path.join(SPECPATH, '..', '..', 'src'))


def _safe_collect_data(pkg):
    try:
        return collect_data_files(pkg)
    except Exception:
        return []


def _safe_collect_libs(pkg):
    try:
        return collect_dynamic_libs(pkg)
    except Exception:
        return []


def _collect_gst_plugins(pkg, plugin_dlls):
    """Collect only specific plugin DLLs from a package's lib/gstreamer-1.0/ dir.

    Returns binaries tuples (src, dest_dir) so PyInstaller analyses each DLL
    for transitive dependencies — same as collect_dynamic_libs but selective.
    """
    import importlib.util
    spec = importlib.util.find_spec(pkg)
    if spec is None:
        return []
    loc = spec.submodule_search_locations[0]
    plugin_dir = os.path.join(loc, 'lib', 'gstreamer-1.0')
    dest = os.path.join(pkg, 'lib', 'gstreamer-1.0')
    return [
        (os.path.join(plugin_dir, dll), dest)
        for dll in plugin_dlls
        if os.path.exists(os.path.join(plugin_dir, dll))
    ]


# Only the plugin DLLs required for H264/RTP reception.
# gstreamer_plugins has 215 plugins (109 MB total) — we cherry-pick the 5 we need.
_REQUIRED_GST_PLUGINS = [
    'gstudp.dll',           # udpsrc
    'gstrtp.dll',           # rtph264depay
    'gstrtpmanager.dll',    # rtpjitterbuffer
    'gstvideoparsersbad.dll',  # h264parse
    'gstlibav.dll',         # avdec_h264
]

a = Analysis(
    [os.path.join(SRC, 'v3xctrl_ui', 'main.py')],
    pathex=[SRC],
    binaries=_safe_collect_libs('gstreamer_libs')
        + _collect_gst_plugins('gstreamer_plugins', _REQUIRED_GST_PLUGINS)
        + _safe_collect_libs('gstreamer_plugins_libs'),
    datas=[(os.path.join(SRC, 'v3xctrl_ui', 'assets'), 'assets')]
        + collect_data_files('material_icons')
        + _safe_collect_data('gstreamer_libs')
        + _safe_collect_data('gstreamer_plugins_libs'),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={
        'gstreamer': {
            'include_plugins': [
                'coreelements',   # pipeline infrastructure
                'app',            # appsink
                'videoconvert',   # videoconvert
                'rtp',            # rtph264depay, rtpjitterbuffer
                'udp',            # udpsrc
                'videoparsers',   # h264parse (gst-plugins-bad)
                'libav',          # avdec_h264
            ],
        },
    },
    runtime_hooks=[os.path.join(SPECPATH, 'runtime_hook_gstreamer.py')],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='V3XCTRL',
    icon=os.path.join(SRC, 'v3xctrl_ui', 'assets', 'images', 'logo.ico'),
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    name='V3XCTRL',
)
