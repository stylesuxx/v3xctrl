"""Build a real Settings for tests, without every test managing a temp file."""

import tempfile
from pathlib import Path
from typing import Any

from v3xctrl_ui.core.Settings import Settings


def build_settings(**overrides: Any) -> Settings:
    """Settings backed by a throwaway file, with the given keys replaced.

    Keys go through Settings.set, so a typed section, a raw table and a plain
    value all work:

        build_settings(ports=PortSettings(video=9999))
        build_settings(ports={"video": 9999}, debug=False)
    """
    settings = Settings(str(Path(tempfile.mkdtemp()) / "settings.toml"))

    for key, value in overrides.items():
        settings.set(key, value)

    return settings
