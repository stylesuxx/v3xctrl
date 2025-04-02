import logging
import pygame
import signal
import time
from collections import deque

from ui.widgets import VerticalIndicatorWidget, HorizontalIndicatorWidget
from ui.widgets import FpsWidget, StatusValueWidget
from ui.helpers import interpolate_steering_color, interpolate_throttle_color, get_fps
from ui.colors import BLACK
from ui.VideoReceiver import VideoReceiver
from ui.KeyAxisHandler import KeyAxisHandler
from ui.menu.Menu import Menu
from ui.Settings import Settings

from rpi_4g_streamer import Server, State
from rpi_4g_streamer.Message import Telemetry, Control


# Settings
WINDOW_TITLE = "RC - Streamer"

FPS_WIDGET_WIDTH = 100
FPS_WIDGET_HEIGHT = 75

FPS_AVERAGE_WINDOW = 30
FPS_GRAPH_FRAMES = 300

settings_path = 'settings.toml'
settings = Settings(settings_path)
controls = settings.get("controls")
ports = settings.get("ports")
debug = settings.get('debug')
framerate = settings.get('fps')
video = settings.get('video')
settings.save()

menu = None


def update_settings():
    global debug, settings_path, settings, menu
    settings = Settings(settings_path)
    debug = settings.get('debug')
    menu = None


loop_history = deque(maxlen=300)

# Control logic state
throttle = 0.0
steering = 0.0
throttle_step = 0.02
steering_speed = 0.05
throttle_friction = 0.01
steering_friction = 0.02

running = True

steering_indicator = HorizontalIndicatorWidget(
    pos=(video["width"] // 2 - 200 - 6, video["height"] - 30 - 6),
    size=(412, 22),
    bar_size=(20, 10),
    range_mode="symmetric",
    color_fn=interpolate_steering_color
)

throttle_indicator = VerticalIndicatorWidget(
    pos=(14, video["height"] - 200 - 20 - 6),
    size=(32, 212),
    bar_width=20,
    range_mode="positive",
    color_fn=interpolate_throttle_color
)

throttle_axis = KeyAxisHandler(
    positive=controls["keyboard"]["throttle_up"],
    negative=controls["keyboard"]["throttle_down"],
    step=throttle_step,
    friction=throttle_friction,
    min_val=0.0,
    max_val=1.0
)

steering_axis = KeyAxisHandler(
    positive=controls["keyboard"]["steering_right"],
    negative=controls["keyboard"]["steering_left"],
    step=steering_speed,
    friction=steering_friction,
    min_val=-1.0,
    max_val=1.0
)

video_receiver = VideoReceiver(ports["video"])
video_receiver.start()

# Pygame setup
pygame.init()
screen = pygame.display.set_mode((video["width"], video["height"]))
pygame.display.set_caption(WINDOW_TITLE)
clock = pygame.time.Clock()

connection_indicator = StatusValueWidget(position=(10, 180), size=20, label="Data")
connection_indicator.set_status("waiting")


def telemetry_handler(message: Telemetry) -> None:
    """ TODO: Implement control message handling. """
    values = message.get_values()
    logging.debug(f"Received telemetry message: {values}")


def disconnect_handler() -> None:
    global connection_indicator
    connection_indicator.set_status("fail")


def connect_handler() -> None:
    global connection_indicator
    connection_indicator.set_status("success")


server = Server(ports["control"])
server.subscribe(Telemetry, telemetry_handler)
server.on(State.DISCONNECTED, disconnect_handler)
server.on(State.CONNECTED, connect_handler)
server.start()

widget_fps_loop = FpsWidget(
    (10, 10),
    (FPS_WIDGET_WIDTH, FPS_WIDGET_HEIGHT),
    "Loop"
)

widget_video_loop = FpsWidget(
    (10, 10 + FPS_WIDGET_HEIGHT + 10),
    (FPS_WIDGET_WIDTH, FPS_WIDGET_HEIGHT),
    "Video"
)

# Game loop FPS tracking
loop_frame_count = 0
last_loop_update = time.time()


def signal_handler(sig, frame):
    global running
    if running:
        running = False
        print("Shutting down...")


signal.signal(signal.SIGINT, signal_handler)

while running:
    loop_history.append(time.time())

    data_left = server.transmitter.queue.qsize()
    connection_indicator.set_value(data_left)

    events = pygame.event.get()
    for event in events:
        if event.type == pygame.QUIT:
            pygame.quit()
            running = False
            break

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if menu is None:
                menu = Menu(video["width"], video["height"], settings, update_settings)
            else:
                menu = None

        elif menu is not None:
            menu.handle_event(event)

    if not running:
        break

    keys = pygame.key.get_pressed()
    throttle_axis.update(keys)
    steering_axis.update(keys)

    throttle = throttle_axis.value
    steering = steering_axis.value

    server.send(Control({
        "steering": steering,
        "throttle": throttle,
        "more": "Here comes some more data to create back pressure..... Here comes some more data to create back pressure..... Here comes some more data to create back pressure..... Here comes some more data to create back pressure..... Here comes some more data to create back pressure..... Here comes some more data to create back pressure.....",
    }))

    with video_receiver.frame_lock:
        if video_receiver.frame is not None:
            surface = pygame.image.frombuffer(video_receiver.frame.tobytes(), (video["width"], video["height"]), "RGB")
            screen.blit(surface, (0, 0))
        else:
            font = pygame.font.SysFont("monospace", 32, bold=True)
            no_signal_text = font.render("No Signal", True, (200, 0, 0))
            text_rect = no_signal_text.get_rect(center=(video["width"] // 2, video["height"] // 2))

            screen.fill(BLACK)
            screen.blit(no_signal_text, text_rect)

    steering_indicator.draw(screen, steering)
    throttle_indicator.draw(screen, throttle)
    connection_indicator.draw(screen)

    if debug:
        widget_fps_loop.draw(screen, get_fps(loop_history))
        widget_video_loop.draw(screen, get_fps(video_receiver.history))

    # Draw menu above everything else
    if menu is not None:
        menu.draw(screen)

    pygame.display.flip()

    clock.tick(framerate)

server.stop()
server.join()

video_receiver.stop()
video_receiver.join()
