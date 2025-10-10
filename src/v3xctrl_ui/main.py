import argparse
from datetime import datetime
import logging

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
parser.add_argument(
    "--log-to-file",
    action="store_true",
    help="Save logs to txt file."
)

args, unknown = parser.parse_known_args()

level_name = args.log.upper()
level = getattr(logging, level_name, None)

if not isinstance(level, int):
    raise ValueError(f"Invalid log level: {args.log}")

log_format = "%(asctime)s - %(levelname)s - %(message)s"
handlers = [logging.StreamHandler()]

if args.log_to_file:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    log_filename = f"{timestamp}.txt"
    handlers.append(logging.FileHandler(log_filename))

logging.basicConfig(
    level=level,
    format=log_format,
    handlers=handlers
)

mem_tracker = None
if args.mem_profile:
    mem_tracker = MemoryTracker(interval=10, top=5)
    mem_tracker.start()

# Load settings from file, otherwise use default values if file not available
settings = Init.settings("settings.toml")
state = AppState(settings)

while state.running:
    if not state.handle_events():
        break

    state.update()
    state.render()

    state.tick()

state.shutdown()

if mem_tracker:
    mem_tracker.stop()
