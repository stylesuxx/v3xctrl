import logging
import pygame
import signal
import time

from ui.colors import BLACK
from ui.menu.Menu import Menu
from ui.Init import Init
from ui.AppState import AppState

from rpi_4g_streamer import State
from rpi_4g_streamer.Message import Telemetry, Control


logging.basicConfig(level=logging.DEBUG)

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

# no UI for those settings
WINDOW_TITLE = settings.get("settings")["title"]
FPS_SETTINGS = settings.get("widgets")["fps"]
STEERING_SETTINGS = settings.get("settings")["steering"]
THROTTLE_SETTINGS = settings.get("settings")["throttle"]


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


def update_settings():
    """ Update settings after exiting menu """
    global debug, controls, settings, state
    settings = Init.settings()

    controls = settings.get("controls")
    debug = settings.get('debug')

    state.menu = None


def render_all(state):
    with state.video_receiver.frame_lock:
        if state.video_receiver.frame is not None:
            surface = pygame.image.frombuffer(state.video_receiver.frame.tobytes(), (VIDEO["width"], VIDEO["height"]), "RGB")
            state.screen.blit(surface, (0, 0))
        else:
            font = pygame.font.SysFont("monospace", 32, bold=True)
            no_signal_text = font.render("No Signal", True, (200, 0, 0))
            text_rect = no_signal_text.get_rect(center=(VIDEO["width"] // 2, VIDEO["height"] // 2))

            state.screen.fill(BLACK)
            state.screen.blit(no_signal_text, text_rect)

    for name, widget in state.widgets.items():
        widget.draw(state.screen, getattr(state, name))

    if debug:
        for name, widget in state.widgets_debug.items():
            widget.draw(state.screen, getattr(state, name))

    # Render errors on top of main UI
    if state.server_error:
        font = pygame.font.SysFont("monospace", 24, bold=True)
        error_text = font.render(state.server_error, True, (255, 50, 50))
        error_rect = error_text.get_rect(center=(VIDEO["width"] // 2, 50))
        state.screen.blit(error_text, error_rect)

    # Draw menu above everything else
    if state.menu is not None:
        state.menu.draw(state.screen)

    pygame.display.flip()


def update_all(state):
    if not state.server_error:
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
