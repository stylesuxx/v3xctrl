import argparse
import logging
import time

from v3xctrl_ui.Init import Init
from v3xctrl_ui.AppState import AppState
from v3xctrl_ui.MemoryTracker import MemoryTracker

parser = argparse.ArgumentParser(description="RC Streamer")
parser.add_argument(
    "--log",
    default="ERROR",
    help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default is ERROR."
)
parser.add_argument(
    "--mem-profile",
    action="store_true",
    help="Enable periodic memory tracking using tracemalloc."
)

args, unknown = parser.parse_known_args()

level_name = args.log.upper()
level = getattr(logging, level_name, None)

if not isinstance(level, int):
    raise ValueError(f"Invalid log level: {args.log}")

logging.basicConfig(
    level=level,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

mem_tracker = None
if args.mem_profile:
    mem_tracker = MemoryTracker(interval=10, top=5)
    mem_tracker.start()

# Load settings from file, otherwise use default values if file not available
settings = Init.settings("settings.toml")

# These settings require restart to take effect
MAIN_LOOP_FPS = settings.get("timing", {}).get("main_loop_fps", 60)
PORTS = settings.get("ports")
VIDEO = settings.get("video")
VIDEO_SIZE = (VIDEO["width"], VIDEO["height"])
WINDOW_TITLE = settings.get("settings")["title"]

state = AppState(
    (VIDEO["width"], VIDEO["height"]),
    WINDOW_TITLE,
    PORTS["video"],
    PORTS["control"],
    settings
)

# Main loop
start_time = time.monotonic()
state.initialize_timing(start_time)

while state.running:
    now = time.monotonic()
    state.loop_history.append(now)

    if not state.handle_events():
        break

    state.update(now)
    state.render()

    state.clock.tick(MAIN_LOOP_FPS)

state.shutdown()

if mem_tracker:
    mem_tracker.stop()
