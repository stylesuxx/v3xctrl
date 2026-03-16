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


a = Analysis(
    [os.path.join(SRC, 'v3xctrl_ui', 'main.py')],
    pathex=[SRC],
    binaries=_safe_collect_libs('gstreamer_libs')
        + _safe_collect_libs('gstreamer_plugins_libs')
        + _safe_collect_libs('gstreamer_plugins_restricted_libs'),
    datas=[(os.path.join(SRC, 'v3xctrl_ui', 'assets'), 'assets')]
        + collect_data_files('material_icons')
        + _safe_collect_data('gstreamer_libs')
        + _safe_collect_data('gstreamer_plugins_libs')
        + _safe_collect_data('gstreamer_plugins_restricted_libs'),
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
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    name='V3XCTRL',
)
