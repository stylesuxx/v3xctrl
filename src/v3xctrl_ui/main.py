import argparse
import logging
import pygame
import signal
import time

from v3xctrl_ui.colors import BLACK, RED, WHITE
from v3xctrl_ui.fonts import BOLD_24_MONO_FONT, BOLD_32_MONO_FONT
from v3xctrl_ui.helpers import get_external_ip
from v3xctrl_ui.GamepadManager import GamepadManager
from v3xctrl_ui.menu.Menu import Menu
from v3xctrl_ui.Init import Init
from v3xctrl_ui.AppState import AppState
from v3xctrl_ui.MemoryTracker import MemoryTracker

from v3xctrl_control import State
from v3xctrl_control.Message import Message, Telemetry, Latency


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
2. Settings that can be hot reloaded
3. Settings for which no UI elements are available (edit via config file only)
"""
settings = Init.settings("settings.toml")

# Those settings can be hot reloaded
debug = settings.get("debug")
input = settings.get("input", {})
widgets = settings.get("widgets", {})
calibrations = settings.get("calibrations", {})
timing = settings.get("timing", {})
main_loop_fps = timing.get("main_loop_fps", 60)
control_rate_frequency = timing.get("control_update_hz", 30)
latency_check_frequency = timing.get("latency_check_hz", 1)
relay = settings.get("relay", {})

control_interval = 1.0 / control_rate_frequency
latency_interval = 1.0 / latency_check_frequency

# Settings require restart to take effect
PORTS = settings.get("ports")
VIDEO = settings.get("video")
VIDEO_SIZE = (VIDEO["width"], VIDEO["height"])

# no UI for those settings
WINDOW_TITLE = settings.get("settings")["title"]

ip = get_external_ip()

if not relay["enabled"]:
    print("================================")
    print(f"IP Address:   {ip}")
    print(f"Video port:   {PORTS['video']}")
    print(f"Control port: {PORTS['control']}")
    print("Make sure to forward this ports!")
    print("================================")


def message_handler(state: AppState, message: Message) -> None:
    state.message_handler(message)


def disconnect_handler(state: AppState) -> None:
    state.disconnect_handler()


def connect_handler(state: AppState) -> None:
    state.connect_handler()


gamepad_manager = GamepadManager()
for guid, calibration in calibrations.items():
    gamepad_manager.set_calibration(guid, calibration)
if "guid" in input:
    gamepad_manager.set_active(input["guid"])
gamepad_manager.start()

handlers = {
    "messages": [
        (Telemetry, lambda message: message_handler(state, message)),
        (Latency, lambda message: message_handler(state, message)),
      ],
    "states": [(State.CONNECTED, lambda: connect_handler(state)),
               (State.DISCONNECTED, lambda: disconnect_handler(state))]
}

state = AppState(
    (VIDEO["width"], VIDEO["height"]),
    WINDOW_TITLE,
    PORTS["video"],
    PORTS["control"],
    handlers,
    settings
)


def update_settings():
    """
    Update settings after exiting menu

    Only update settings that can be hot reloaded, some settings need a restart
    of the application, we do not update those.
    """
    global debug, state, widgets, main_loop_fps
    global control_interval, latency_interval

    settings = Init.settings()

    debug = settings.get('debug')
    widgets = settings.get('widgets', {})

    timing = settings.get("timing", {})
    main_loop_fps = timing.get('main_loop_fps', 60)

    control_rate_frequency = timing.get('control_update_hz', 30)
    control_interval = 1.0 / control_rate_frequency

    latency_check_frequency = timing.get('latency_check_hz', 30)
    latency_interval = 1.0 / latency_check_frequency

    input = settings.get("input", {})
    calibrations = settings.get("calibrations", {})
    for guid, calibration in calibrations.items():
        gamepad_manager.set_calibration(guid, calibration)
    if "guid" in input:
        gamepad_manager.set_active(input["guid"])

    state.update_settings(settings)


def render_all(state):
    frame = None
    if state.video_receiver:
        with state.video_receiver.frame_lock:
            frame = state.video_receiver.frame
            if frame is not None:
                surface = pygame.image.frombuffer(frame.tobytes(),
                                                  VIDEO_SIZE,
                                                  "RGB")
                state.screen.blit(surface, (0, 0))

    if frame is None:
        surface, rect = BOLD_32_MONO_FONT.render("No Signal", RED)
        rect.center = (VIDEO["width"] // 2, VIDEO["height"] // 2 - 40)

        state.screen.fill(BLACK)
        state.screen.blit(surface, rect)

        if relay["enabled"]:
            surface, rect = BOLD_32_MONO_FONT.render(state.relay_status_message, RED)
            rect.center = (VIDEO["width"] // 2, VIDEO["height"] // 2 + 10)
            state.screen.blit(surface, rect)

        if not relay["enabled"]:
            info_data = [
                ("Host", ip),
                ("Video", str(PORTS['video'])),
                ("Control", str(PORTS['control'])),
            ]

            key_x = VIDEO["width"] // 2 - 140
            val_x = VIDEO["width"] // 2 - 10
            base_y = VIDEO["height"] // 2 + 10
            line_height = 36

            for i, (key, val) in enumerate(info_data):
                y = base_y + i * line_height
                key_surf, key_rect = BOLD_24_MONO_FONT.render(f"{key}:", WHITE)
                key_rect.topleft = (key_x, y)
                state.screen.blit(key_surf, key_rect)

                val_surf, val_rect = BOLD_24_MONO_FONT.render(val, WHITE)
                val_rect.topleft = (val_x, y)
                state.screen.blit(val_surf, val_rect)

    state.render_widgets()

    # Render errors on top of main UI
    if state.server_error:
        surface, rect = BOLD_24_MONO_FONT.render(state.server_error, RED)
        rect.center = (VIDEO["width"] // 2, 50)
        state.screen.blit(surface, rect)

    # Draw menu above everything else
    if state.menu is not None:
        state.menu.draw(state.screen)

    pygame.display.flip()


def handle_control(state: AppState):
    pressed_keys = pygame.key.get_pressed()
    gamepad_inputs = gamepad_manager.read_inputs()

    state.handle_control(pressed_keys, gamepad_inputs)


def handle_events(state):
    events = pygame.event.get()
    for event in events:
        if event.type == pygame.QUIT:
            state.running = False
            return

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if state.menu is None:
                state.menu = Menu(
                    VIDEO["width"],
                    VIDEO["height"],
                    gamepad_manager,
                    settings,
                    update_settings,
                    state.server)
            else:
                state.menu = None

        elif state.menu is not None:
            state.menu.handle_event(event)


def signal_handler(sig, frame, state):
    if state.running:
        state.running = False
        print("Shutting down...")


signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, state))

if relay["enabled"]:
    state.setup_relay(relay["server"], relay["id"])

state.setup_ports()

# Main loop
last_control_update = time.monotonic()
last_latency_check = last_control_update
while state.running:
    now = time.monotonic()
    state.loop_history.append(time.time())

    handle_events(state)
    if not state.running:
        break

    if now - last_control_update >= control_interval:
        handle_control(state)
        last_control_update = now

    # Send latency message
    if now - last_latency_check >= latency_interval:
        if state.server and not state.server_error:
            state.server.send(Latency())
        last_latency_check = now

    render_all(state)

    state.clock.tick(main_loop_fps)


gamepad_manager.stop()
state.shutdown()

if mem_tracker:
    mem_tracker.stop()
