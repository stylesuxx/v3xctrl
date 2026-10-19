"""Locating files that ship with the viewer."""

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parent.parent


def get_resource_path(relative_path: str) -> Path:
    """An asset shipped with the viewer, from source or from a PyInstaller bundle.

    A one-file bundle unpacks to a temporary directory named by `sys._MEIPASS`,
    which only exists in that case.
    """
    bundle_root = getattr(sys, "_MEIPASS", None)
    base_path = Path(bundle_root) if bundle_root else PACKAGE_ROOT

    return base_path / relative_path
