"""Checks that fail a run before it touches the streamer."""

import os
import socket
from collections.abc import Callable
from typing import Any

from v3xctrl_relay.helper import test_relay_connection
from v3xctrl_ui.utils.gstreamer import is_gstreamer_available

UINPUT_PATH = "/dev/uinput"


def check_agent(ping: Callable[[], dict[str, Any]]) -> list[str]:
    try:
        response = ping()
    except Exception as error:
        return [f"streamer agent: {error}"]

    if not response.get("package_version"):
        return ["streamer agent: v3xctrl package not installed on the streamer"]

    return []


def check_load(load: dict[str, Any], maximum_load_per_cpu: float) -> list[str]:
    one_minute = float(load["load_average"][0])
    cpu_count = int(load["cpu_count"])
    per_cpu = one_minute / cpu_count
    if per_cpu > maximum_load_per_cpu:
        return [
            f"streamer load: 1 minute load average {one_minute:.2f} on {cpu_count} CPUs "
            f"is above {maximum_load_per_cpu:.2f} per CPU; stop whatever else is running on the Pi"
        ]

    return []


def check_local_ports(ports: list[int]) -> list[str]:
    failures: list[str] = []
    for port in ports:
        for family_name, socket_type in (("UDP", socket.SOCK_DGRAM), ("TCP", socket.SOCK_STREAM)):
            with socket.socket(socket.AF_INET, socket_type) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind(("0.0.0.0", port))
                except OSError:
                    failures.append(f"local port {port}/{family_name} is in use")

    return failures


def check_uinput(path: str = UINPUT_PATH) -> list[str]:
    if not os.path.exists(path):
        return [f"{path} does not exist; load the uinput kernel module"]

    if not os.access(path, os.W_OK):
        return [f"{path} is not writable; install e2e/udev/70-v3xctrl-e2e-uinput.rules and re-login"]

    return []


def check_display(headless: bool, environment: dict[str, str] | None = None) -> list[str]:
    if headless:
        return []

    variables = environment if environment is not None else dict(os.environ)
    if variables.get("DISPLAY") or variables.get("WAYLAND_DISPLAY"):
        return []

    return ["no DISPLAY or WAYLAND_DISPLAY; run inside a desktop session or pass --headless"]


def check_gstreamer() -> list[str]:
    if not is_gstreamer_available():
        return ["GStreamer receiver not available in the viewer interpreter"]

    return []


REQUIRED_VIEWER_FLAGS = ("--connect", "--config", "--log")
TITLE_VIEWER_FLAG = "--title"


def check_viewer_flags(help_text: str) -> list[str]:
    """The harness drives the viewer purely through these flags; an older build lacks `--connect`."""
    missing = [flag for flag in REQUIRED_VIEWER_FLAGS if flag not in help_text]
    if missing:
        return [
            f"viewer under test does not support {', '.join(missing)}; it needs a build from a branch with issue #691's viewer changes"
        ]

    return []


def has_viewer_titles(help_text: str) -> bool:
    """Window titles name the running case; a build without the flag runs untitled."""
    return TITLE_VIEWER_FLAG in help_text


def check_relay(host: str, port: int, session_id: str) -> list[str]:
    success, message = test_relay_connection(host, port, session_id, False)
    if not success:
        return [f"relay {host}:{port}: {message}"]

    return []


def split_relay_host(relay_host: str, default_port: int = 8888) -> tuple[str, int]:
    host, separator, port = relay_host.rpartition(":")
    if separator and port.isdigit():
        return host, int(port)

    return relay_host, default_port
