"""Builds the viewer's settings.toml for one permutation."""

from dataclasses import dataclass
from typing import Any

import tomli_w

from v3xctrl_e2e.matrix import WRONG_RELAY_ID, ConnectionMode, TestCase

DEFAULT_VIDEO_PORT = 16384
DEFAULT_CONTROL_PORT = 16386


@dataclass(frozen=True)
class GamepadBinding:
    """How the virtual gamepad's axes and buttons appear to pygame."""

    guid: str
    throttle_axis: int
    steering_axis: int
    brake_axis: int
    trim_increase_button: int
    trim_decrease_button: int
    rec_toggle_button: int


def calibration_for(binding: GamepadBinding) -> dict[str, Any]:
    """A calibration block for an ideal device: full range, centred, no dead band.

    The viewer reads the brake axis unconditionally, so one is always bound.
    """
    centred_axis = {"min": -1.0, "center": 0.0, "max": 1.0, "invert": False, "deadband": 0}
    return {
        "throttle": {"axis": binding.throttle_axis, **centred_axis},
        "steering": {"axis": binding.steering_axis, **centred_axis},
        "brake": {"axis": binding.brake_axis, "min": -1.0, "max": 1.0, "invert": False, "deadband": 0},
        "buttons": {
            "trim_increase": binding.trim_increase_button,
            "trim_decrease": binding.trim_decrease_button,
            "rec_toggle": binding.rec_toggle_button,
        },
    }


def build_viewer_settings(
    test_case: TestCase,
    relay_host: str,
    relay_id: str,
    gamepad: GamepadBinding | None,
    video_port: int = DEFAULT_VIDEO_PORT,
    control_port: int = DEFAULT_CONTROL_PORT,
) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "transport": str(test_case.viewer_transport),
        "ports": {"video": video_port, "control": control_port},
        "relay": {
            "enabled": test_case.mode == ConnectionMode.RELAY,
            "server": relay_host,
            "id": WRONG_RELAY_ID if test_case.wrong_relay_id else relay_id,
            "spectator_mode": False,
        },
        "video": {"receiver": "auto"},
    }

    if gamepad is not None:
        settings["input"] = {"guid": gamepad.guid}
        settings["calibrations"] = {gamepad.guid: calibration_for(gamepad)}

    return settings


SPECTATOR_VIDEO_PORT = 16388
SPECTATOR_CONTROL_PORT = 16390


def build_spectator_settings(
    test_case: TestCase,
    relay_host: str,
    spectator_id: str,
    video_port: int = SPECTATOR_VIDEO_PORT,
    control_port: int = SPECTATOR_CONTROL_PORT,
) -> dict[str, Any]:
    """A second viewer on the same machine, so it needs its own local ports."""
    return {
        "transport": str(test_case.viewer_transport),
        "ports": {"video": video_port, "control": control_port},
        "relay": {
            "enabled": True,
            "server": relay_host,
            "id": spectator_id,
            "spectator_mode": True,
        },
        "video": {"receiver": "auto"},
    }


def render_settings(settings: dict[str, Any]) -> str:
    # The CI typecheck job runs mypy without third-party packages, so the
    # library's return type is Any there and the contract is pinned here.
    text: str = tomli_w.dumps(settings)
    return text
