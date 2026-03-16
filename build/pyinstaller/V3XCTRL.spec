# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

a = Analysis(
    ['v3xctrl_ui/main.py'],
    pathex=['.'],
    binaries=collect_dynamic_libs('gstreamer_libs'),
    datas=[('v3xctrl_ui/assets', 'assets')]
        + collect_data_files('material_icons')
        + collect_data_files('gstreamer_libs'),
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
    runtime_hooks=['../build/pyinstaller/runtime_hook_gstreamer.py'],
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
    icon='v3xctrl_ui/assets/images/logo.ico',
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
