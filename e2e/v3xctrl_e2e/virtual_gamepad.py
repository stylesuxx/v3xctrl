"""A uinput gamepad the viewer sees as a real joystick.

evdev is imported inside the methods that need it, so the harness can be
imported, type checked and unit tested on a machine without it.
"""

import subprocess
from enum import StrEnum
from typing import Any

from v3xctrl_e2e.viewer_config import GamepadBinding

DEVICE_NAME = "v3xctrl e2e gamepad"
VENDOR_ID = 0x1209
PRODUCT_ID = 0xE2E0
DEVICE_VERSION = 1
BUS_USB = 0x03

AXIS_MAXIMUM = 32767

EV_KEY = 0x01
EV_ABS = 0x03

ABS_X = 0x00
ABS_Y = 0x01
ABS_RZ = 0x05

BTN_SOUTH = 0x130
BTN_TL = 0x136
BTN_TR = 0x137


class Axis(StrEnum):
    STEERING = "steering"
    THROTTLE = "throttle"
    BRAKE = "brake"


class Button(StrEnum):
    REC_TOGGLE = "rec_toggle"
    TRIM_DECREASE = "trim_decrease"
    TRIM_INCREASE = "trim_increase"


AXIS_CODES: dict[Axis, int] = {Axis.STEERING: ABS_X, Axis.THROTTLE: ABS_Y, Axis.BRAKE: ABS_RZ}
BUTTON_CODES: dict[Button, int] = {
    Button.REC_TOGGLE: BTN_SOUTH,
    Button.TRIM_DECREASE: BTN_TL,
    Button.TRIM_INCREASE: BTN_TR,
}

# The brake rests at its minimum so the viewer reads it as zero
AXIS_REST_VALUES: dict[Axis, int] = {Axis.STEERING: 0, Axis.THROTTLE: 0, Axis.BRAKE: -AXIS_MAXIMUM}


def sdl_axis_index(axis: Axis) -> int:
    """SDL numbers joystick axes by ascending evdev code."""
    ordered = sorted(AXIS_CODES.values())
    return ordered.index(AXIS_CODES[axis])


def sdl_button_index(button: Button) -> int:
    """SDL numbers joystick buttons by ascending evdev code, starting at BTN_JOYSTICK."""
    ordered = sorted(BUTTON_CODES.values())
    return ordered.index(BUTTON_CODES[button])


def binding_for(guid: str) -> GamepadBinding:
    return GamepadBinding(
        guid=guid,
        throttle_axis=sdl_axis_index(Axis.THROTTLE),
        steering_axis=sdl_axis_index(Axis.STEERING),
        brake_axis=sdl_axis_index(Axis.BRAKE),
        trim_increase_button=sdl_button_index(Button.TRIM_INCREASE),
        trim_decrease_button=sdl_button_index(Button.TRIM_DECREASE),
        rec_toggle_button=sdl_button_index(Button.REC_TOGGLE),
    )


def axis_raw_value(value: float) -> int:
    clamped = max(-1.0, min(1.0, value))
    return round(clamped * AXIS_MAXIMUM)


class VirtualGamepad:
    def __init__(self) -> None:
        self._device: Any | None = None

    def open(self) -> None:
        import evdev
        from evdev import AbsInfo, ecodes

        absolute_axes = [
            (
                code,
                AbsInfo(
                    value=AXIS_REST_VALUES[axis], min=-AXIS_MAXIMUM, max=AXIS_MAXIMUM, fuzz=0, flat=0, resolution=0
                ),
            )
            for axis, code in AXIS_CODES.items()
        ]
        events: dict[int, Any] = {ecodes.EV_ABS: absolute_axes, ecodes.EV_KEY: list(BUTTON_CODES.values())}
        self._device = evdev.UInput(
            events=events,
            name=DEVICE_NAME,
            vendor=VENDOR_ID,
            product=PRODUCT_ID,
            version=DEVICE_VERSION,
            bustype=BUS_USB,
        )
        for axis in Axis:
            self._write_axis(axis, AXIS_REST_VALUES[axis])

    def close(self) -> None:
        if self._device is not None:
            self._device.close()
            self._device = None

    def set_axis(self, axis: Axis, value: float) -> None:
        self._write_axis(axis, axis_raw_value(value))

    def release_all(self) -> None:
        for axis in Axis:
            self._write_axis(axis, AXIS_REST_VALUES[axis])

    def press(self, button: Button) -> None:
        self._write_key(BUTTON_CODES[button], 1)

    def release(self, button: Button) -> None:
        self._write_key(BUTTON_CODES[button], 0)

    def _write_axis(self, axis: Axis, raw_value: int) -> None:
        device = self._require_device()
        device.write(EV_ABS, AXIS_CODES[axis], raw_value)
        device.syn()

    def _write_key(self, code: int, state: int) -> None:
        device = self._require_device()
        device.write(EV_KEY, code, state)
        device.syn()

    def _require_device(self) -> Any:
        if self._device is None:
            raise RuntimeError("virtual gamepad is not open")
        return self._device


DISCOVERY_SCRIPT = """
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

name = sys.argv[1]
deadline = time.monotonic() + float(sys.argv[2])

pygame.init()
while True:
    pygame.joystick.quit()
    pygame.joystick.init()
    for index in range(pygame.joystick.get_count()):
        joystick = pygame.joystick.Joystick(index)
        if joystick.get_name() == name:
            print(joystick.get_guid(), joystick.get_numaxes(), joystick.get_numbuttons())
            sys.exit(0)

    if time.monotonic() > deadline:
        sys.exit(1)

    time.sleep(0.5)
"""


def discover_guid(python_executable: str, timeout_seconds: float = 10.0) -> str:
    """Ask pygame, in the viewer's interpreter, which GUID it assigns to the virtual gamepad."""
    completed = subprocess.run(
        [python_executable, "-c", DISCOVERY_SCRIPT, DEVICE_NAME, str(timeout_seconds)],
        capture_output=True,
        text=True,
        timeout=timeout_seconds + 10.0,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"pygame did not see '{DEVICE_NAME}' within {timeout_seconds}s: {completed.stderr.strip()}")

    guid, axes, buttons = completed.stdout.split()[-3:]
    if int(axes) != len(AXIS_CODES) or int(buttons) != len(BUTTON_CODES):
        raise RuntimeError(f"pygame reports {axes} axes and {buttons} buttons for '{DEVICE_NAME}'")

    return guid
