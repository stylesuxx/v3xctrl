"""Per-frame render cost for the viewer's hot path.

Drives the Renderer against a fake video receiver at 1280x720 and reports the
wall time of one rendered frame, split into the work that assembles the frame's
data and the work that draws it.

Numbers are machine specific and there is no committed baseline. Run it on the
same machine before and after a change and compare the two outputs.

    python benchmarks/render_frame.py [--frames N]
"""

import argparse
import os
import statistics
import tempfile
import time
from collections import deque
from pathlib import Path

import numpy as np
import numpy.typing as npt

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from v3xctrl_ui.core.dataclasses import ApplicationModel
from v3xctrl_ui.core.FrameSnapshot import ConnectionStatus, FrameSnapshot
from v3xctrl_ui.core.Renderer import Renderer
from v3xctrl_ui.core.Settings import Settings
from v3xctrl_ui.core.TelemetryContext import TelemetryContext
from v3xctrl_ui.osd.OSD import OSD

WIDTH = 1280
HEIGHT = 720
WARMUP_FRAMES = 200


class FakeReceiver:
    """Stands in for a video receiver at the seam the Renderer reads from.

    Hands out a different array object on every call, so the Renderer's
    identity check sees a new frame and blits it. That is the expensive path
    and the one worth measuring.
    """

    RING_SIZE = 4

    def __init__(self, width: int, height: int) -> None:
        rng = np.random.default_rng(seed=1)
        # Decoded frames arrive row-major; the Renderer swaps axes before blitting.
        self.ring: list[npt.NDArray[np.uint8]] = [
            rng.integers(0, 256, (height, width, 3), dtype=np.uint8) for _ in range(self.RING_SIZE)
        ]
        self.render_history: deque[float] = deque([time.monotonic()] * 100, maxlen=100)
        self.frame_buffer: deque[npt.NDArray[np.uint8]] = deque(maxlen=300)
        self.get_frame_calls = 0

    def get_frame(self) -> npt.NDArray[np.uint8]:
        frame = self.ring[self.get_frame_calls % self.RING_SIZE]
        self.get_frame_calls += 1
        self.render_history.append(time.monotonic())
        return frame


class FakeNetworkController:
    """Stands in for the control channel the Renderer reads status from."""

    def __init__(self, receiver: FakeReceiver) -> None:
        self.video_receiver = receiver
        self.server_error: str | None = None
        self.relay_enable = False
        self.relay_status_message = "Waiting for streamer..."
        self.relay_spectator_mode = False
        self.control_buffer_calls = 0

    def get_control_buffer_size(self) -> int:
        self.control_buffer_calls += 1
        return 1


class FakeMenu:
    visible = False

    def draw(self, surface: pygame.Surface) -> None:
        pass


def percentiles(samples_ns: list[int]) -> tuple[float, float, float]:
    ordered = sorted(samples_ns)
    count = len(ordered)

    def at(fraction: float) -> float:
        index = min(count - 1, int(fraction * count))
        return ordered[index] / 1_000_000

    return at(0.5), at(0.95), at(0.99)


def report(label: str, samples_ns: list[int]) -> None:
    p50, p95, p99 = percentiles(samples_ns)
    mean_ms = statistics.fmean(samples_ns) / 1_000_000
    print(f"  {label:<24} p50 {p50:6.3f} ms   p95 {p95:6.3f} ms   p99 {p99:6.3f} ms   mean {mean_ms:6.3f} ms")


def build_settings() -> Settings:
    config_path = Path(tempfile.mkdtemp(prefix="v3xctrl-benchmark-")) / "settings.toml"
    return Settings(str(config_path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=2000, help="Frames to measure after warmup. Default 2000.")
    arguments = parser.parse_args()

    settings = build_settings()
    telemetry_context = TelemetryContext()

    pygame.display.set_mode((WIDTH, HEIGHT), pygame.DOUBLEBUF | pygame.SCALED)
    screen = pygame.display.get_surface()

    osd = OSD(settings, telemetry_context)
    menu = FakeMenu()
    receiver = FakeReceiver(WIDTH, HEIGHT)
    controller = FakeNetworkController(receiver)

    renderer = Renderer((WIDTH, HEIGHT), settings, osd, menu)

    model = ApplicationModel(user_connected=True, control_connected=True, throttle=0.42, steering=-0.18)
    model.loop_history.extend([time.monotonic()] * 300)

    def build_snapshot() -> FrameSnapshot:
        connection = ConnectionStatus(
            user_connected=True,
            control_connected=True,
            server_error=controller.server_error,
            relay_enabled=controller.relay_enable,
            relay_status_message=controller.relay_status_message,
            control_queue_depth=controller.get_control_buffer_size(),
            video_buffer_depth=len(receiver.frame_buffer),
        )

        osd.update_buffer_queue(connection.video_buffer_depth)
        osd.update_control_queue(connection.control_queue_depth)
        osd.set_control(model.throttle, model.steering)
        osd.set_spectator_mode(connection.spectator)

        return FrameSnapshot(
            connection=connection,
            video_frame=receiver.get_frame(),
            throttle=model.throttle,
            steering=model.steering,
            fullscreen=model.fullscreen,
            scale=model.scale,
            menu_visible=menu.visible,
            loop_history=model.loop_history.copy(),
            video_history=receiver.render_history.copy(),
        )

    snapshot_samples_ns: list[int] = []
    frame_samples_ns: list[int] = []

    def render_one_frame(record: bool) -> None:
        start = time.perf_counter_ns()
        snapshot = build_snapshot()
        built = time.perf_counter_ns()
        renderer.render(screen, snapshot)
        done = time.perf_counter_ns()

        if record:
            snapshot_samples_ns.append(built - start)
            frame_samples_ns.append(done - start)

    for _ in range(WARMUP_FRAMES):
        render_one_frame(record=False)

    for _ in range(arguments.frames):
        render_one_frame(record=True)

    print(f"\nrender_frame  {WIDTH}x{HEIGHT}  {arguments.frames} frames after {WARMUP_FRAMES} warmup")
    report("snapshot build", snapshot_samples_ns)
    report("full frame", frame_samples_ns)
    total_frames = arguments.frames + WARMUP_FRAMES
    print(f"\n  get_frame calls per frame          {receiver.get_frame_calls / total_frames:.2f}")
    print(f"  get_control_buffer_size per frame  {controller.control_buffer_calls / total_frames:.2f}\n")

    pygame.quit()


if __name__ == "__main__":
    main()
