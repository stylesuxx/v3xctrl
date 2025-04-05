import argparse
import logging
import pygame
import pygame.freetype
import signal
import time

from ui.colors import BLACK, RED
from ui.helpers import get_external_ip
from ui.menu.Menu import Menu
from ui.Init import Init
from ui.AppState import AppState
from ui.MemoryTracker import MemoryTracker

from rpi_4g_streamer import State
from rpi_4g_streamer.Message import Telemetry, Control


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

"""
Load settings from file.

We have different kind of settings:
1. Settings that require restart to take effect (e.g. ports, video settings)
2. Settings that can be hot reloaded (e.g. controls, debug)
3. Settings for which no UI elements are available (edit via config file only)
"""
settings = Init.settings("settings.toml")

# Those settings can be hot reloaded
controls = settings.get("controls")
debug = settings.get("debug")

# Settings require restart to take effect
PORTS = settings.get("ports")
VIDEO = settings.get("video")
FRAMERATE = settings.get('fps')
VIDEO_SIZE = (VIDEO["width"], VIDEO["height"])

# no UI for those settings
WINDOW_TITLE = settings.get("settings")["title"]
FPS_SETTINGS = settings.get("widgets")["fps"]
STEERING_SETTINGS = settings.get("settings")["steering"]
THROTTLE_SETTINGS = settings.get("settings")["throttle"]

ip = get_external_ip()
print("================================")
print(f"IP Address:   {ip}")
print(f"Video port:   {PORTS['video']}")
print(f"Control port: {PORTS['control']}")
print("Make sure to forward this ports!")
print("================================")


def telemetry_handler(state: AppState, message: Telemetry) -> None:
    """ TODO: Implement control message handling. """
    values = message.get_values()
    logging.debug(f"Received telemetry message: {values}")


def disconnect_handler(state) -> None:
    state.data = "fail"


def connect_handler(state) -> None:
    state.data = "success"


handlers = {
    "messages": [(Telemetry, lambda m: telemetry_handler(state, m))],
    "states": [(State.CONNECTED, lambda: connect_handler(state)),
               (State.DISCONNECTED, lambda: disconnect_handler(state))]
}

state = AppState((VIDEO["width"], VIDEO["height"]),
                 WINDOW_TITLE,
                 PORTS["video"],
                 PORTS["control"],
                 handlers,
                 FPS_SETTINGS,
                 controls["keyboard"],
                 THROTTLE_SETTINGS,
                 STEERING_SETTINGS)

FONTS = {
    "mono_bold_24": pygame.freetype.SysFont("monospace", 24, bold=True),
    "mono_bold_32": pygame.freetype.SysFont("monospace", 32, bold=True),
}


def update_settings():
    """ Update settings after exiting menu """
    global debug, controls, settings, state
    settings = Init.settings()

    controls = settings.get("controls")
    debug = settings.get('debug')

    state.menu = None


def render_all(state):
    with state.video_receiver.frame_lock:
        frame = state.video_receiver.frame
        if frame is not None:
            surface = pygame.image.frombuffer(frame.tobytes(),
                                              VIDEO_SIZE,
                                              "RGB")
            state.screen.blit(surface, (0, 0))
        else:
            surface, rect = FONTS["mono_bold_32"].render("No Signal", RED)
            rect.center = (VIDEO["width"] // 2, VIDEO["height"] // 2)

            state.screen.fill(BLACK)
            state.screen.blit(surface, rect)

    for name, widget in state.widgets.items():
        widget.draw(state.screen, getattr(state, name))

    if debug:
        for name, widget in state.widgets_debug.items():
            widget.draw(state.screen, getattr(state, name))

    # Render errors on top of main UI
    if state.server_error:
        surface, rect = FONTS["mono_bold_24"].render(state.server_error, RED)
        rect.center = (VIDEO["width"] // 2, 50)
        state.screen.blit(surface, rect)

    # Draw menu above everything else
    if state.menu is not None:
        state.menu.draw(state.screen)

    pygame.display.flip()


def update_all(state):
    if not state.server_error and "data" in state.widgets:
        data_left = state.server.transmitter.queue.qsize()
        state.widgets["data"].set_value(data_left)
    else:
        state.data = "fail"

    keys = pygame.key.get_pressed()
    state.throttle = state.key_handlers["throttle"].update(keys)
    state.steering = state.key_handlers["steering"].update(keys)

    if not state.server_error:
        state.server.send(Control({
            "steering": state.steering,
            "throttle": state.throttle,
        }))


def handle_events(state):
    events = pygame.event.get()
    for event in events:
        if event.type == pygame.QUIT:
            state.running = False
            return

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if state.menu is None:
                state.menu = Menu(VIDEO["width"], VIDEO["height"], settings, update_settings)
            else:
                state.menu = None

        elif state.menu is not None:
            state.menu.handle_event(event)


def signal_handler(sig, frame, state):
    if state.running:
        state.running = False
        print("Shutting down...")


signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, state))

while state.running:
    state.loop_history.append(time.time())

    handle_events(state)
    if not state.running:
        break

    update_all(state)
    render_all(state)

    state.clock.tick(FRAMERATE)

state.shutdown()

if mem_tracker:
    mem_tracker.stop()
