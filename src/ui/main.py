import pygame
import signal
import time
from collections import deque

from ui.widgets import VerticalIndicatorWidget, HorizontalIndicatorWidget
from ui.widgets import FpsWidget, StatusWidget
from ui.helpers import interpolate_steering_color, interpolate_throttle_color
from ui.colors import BLACK
from ui.VideoReceiver import VideoReceiver
from ui.KeyAxisHandler import KeyAxisHandler

# Settings
WINDOW_TITLE = "RC - Streamer"
PORT = 6666
WIDTH, HEIGHT = 1280, 720
LOOP_HZ = 60
DEBUG_OVERLAY = True

FPS_WIDGET_WIDTH = 100
FPS_WIDGET_HEIGHT = 75

FPS_AVERAGE_WINDOW = 30
FPS_GRAPH_FRAMES = 300

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
    pos=(WIDTH // 2 - 200 - 6, HEIGHT - 30 - 6),
    size=(412, 22),
    bar_size=(20, 10),
    range_mode="symmetric",
    color_fn=interpolate_steering_color
)

throttle_indicator = VerticalIndicatorWidget(
    pos=(14, HEIGHT - 200 - 20 - 6),
    size=(32, 212),
    bar_width=20,
    range_mode="positive",
    color_fn=interpolate_throttle_color
)

throttle_axis = KeyAxisHandler(
    positive=pygame.K_w,
    negative=pygame.K_s,
    step=throttle_step,
    friction=throttle_friction,
    min_val=0.0,
    max_val=1.0
)

steering_axis = KeyAxisHandler(
    positive=pygame.K_d,
    negative=pygame.K_a,
    step=steering_speed,
    friction=steering_friction,
    min_val=-1.0,
    max_val=1.0
)

video_receiver = VideoReceiver(PORT)
video_receiver.start()

# Pygame setup
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption(WINDOW_TITLE)
clock = pygame.time.Clock()

connection_indicator = StatusWidget(position=(10, 180), size=20, label="Data")
connection_indicator.set_status("waiting")

if DEBUG_OVERLAY:
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
    running = False
    print("Shutting down...")


signal.signal(signal.SIGINT, signal_handler)

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            running = False

    if not running:
        break

    keys = pygame.key.get_pressed()
    throttle_axis.update(keys)
    steering_axis.update(keys)

    throttle = throttle_axis.value
    steering = steering_axis.value

    loop_fps = clock.get_fps()
    loop_history.append(loop_fps)

    with video_receiver.frame_lock:
        if video_receiver.frame is not None:
            surface = pygame.image.frombuffer(video_receiver.frame.tobytes(), (WIDTH, HEIGHT), "RGB")
            screen.blit(surface, (0, 0))
        else:
            font = pygame.font.SysFont("monospace", 32, bold=True)
            no_signal_text = font.render("No Signal", True, (200, 0, 0))
            text_rect = no_signal_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))

            screen.fill(BLACK)
            screen.blit(no_signal_text, text_rect)

    steering_indicator.draw(screen, steering)
    throttle_indicator.draw(screen, throttle)
    connection_indicator.draw(screen)

    if DEBUG_OVERLAY:
        widget_fps_loop.draw(screen, loop_history)
        widget_video_loop.draw(screen, video_receiver.history)

    pygame.display.flip()

    clock.tick(LOOP_HZ)

video_receiver.stop()
video_receiver.join()
