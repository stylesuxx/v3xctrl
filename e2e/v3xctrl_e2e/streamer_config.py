"""Builds the streamer's config.json for one permutation.

The `network` section is carried over from the live config untouched: it
holds the WiFi settings, and rewriting it can drop the Pi off the LAN.
"""

import copy
import json
from pathlib import Path
from typing import Any

from v3xctrl_e2e.matrix import WRONG_RELAY_ID, ConnectionMode, TestCase

SHIPPED_CONFIG_PATH = Path(__file__).resolve().parents[2] / "build/packages/v3xctrl/data/config/config.json"

STREAMER_LOG_LEVEL = "DEBUG"


def load_shipped_defaults(path: Path = SHIPPED_CONFIG_PATH) -> dict[str, Any]:
    with path.open("rb") as handle:
        loaded: dict[str, Any] = json.load(handle)
        return loaded


def build_streamer_config(
    live_config: dict[str, Any],
    shipped_defaults: dict[str, Any],
    test_case: TestCase,
    viewer_host: str,
    relay_host: str,
    relay_id: str,
    use_camera: bool = False,
) -> dict[str, Any]:
    config = copy.deepcopy(live_config)
    config["viewer"] = copy.deepcopy(shipped_defaults["viewer"])

    viewer = config["viewer"]
    viewer["mode"] = str(test_case.mode)
    viewer["transport"] = str(test_case.streamer_transport)
    viewer["direct"]["host"] = viewer_host
    viewer["relay"]["host"] = relay_host
    viewer["relay"]["sessionId"] = WRONG_RELAY_ID if test_case.wrong_relay_id else relay_id

    config.setdefault("development", {})["logLevel"] = STREAMER_LOG_LEVEL

    # The service manager only starts the video service when autostart is on,
    # and the shipped default is off.
    video = config.setdefault("video", {})
    video["autostart"] = True
    video["testSource"] = not use_camera

    return config


def telemetry_send_rate(config: dict[str, Any]) -> float:
    rate = config.get("telemetry", {}).get("sendRate", 1.0)
    return float(rate)


def source_framerate(config: dict[str, Any]) -> int:
    """The frame rate from `video.resolution`, written as `1280x720@30`."""
    resolution = str(config.get("video", {}).get("resolution", "1280x720@30"))
    _, _, framerate = resolution.partition("@")
    return int(framerate) if framerate.isdigit() else 30


def recording_directory(config: dict[str, Any]) -> str:
    directory = config.get("video", {}).get("record", {}).get("path", "/data/recordings")
    return str(directory)


def is_relay_mode(test_case: TestCase) -> bool:
    return test_case.mode == ConnectionMode.RELAY
