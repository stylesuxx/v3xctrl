import pygame
from pygame.freetype import SysFont
from ui.menu.Button import Button
from ui.menu.Select import Select
from ui.colors import WHITE, GREY, DARK_GREY
from ui.calibration.GamepadCalibrator import GamepadCalibrator, CalibratorState
import threading

# Constants for tuning
AXIS_MOVEMENT_THRESHOLD = 0.3
FRAME_CONFIRMATION_COUNT = 15
STABLE_FRAME_COUNT = 60
IDLE_SAMPLE_COUNT = 10
PAUSE_DURATION_MS = 3000

pygame.init()
size = (1280, 720)
screen = pygame.display.set_mode(size, pygame.DOUBLEBUF | pygame.SCALED)
pygame.display.set_caption("Gamepad Calibration")
clock = pygame.time.Clock()
font = SysFont("Arial", 24)

calibrator = None
calibration_running = False

# Gamepad state
gamepads = []
gamepad_names = []
selected_gamepad = 0


def refresh_gamepads():
    global gamepads, gamepad_names
    gamepads = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    for g in gamepads:
        g.init()
    gamepad_names = [g.get_name() for g in gamepads]


refresh_gamepads()


def start_calibration():
    global calibrator, calibration_running
    if calibration_running:
        return

    calibration_running = True

    def on_done():
        calibrate_button.enable()
        controller_select.enable()

        settings = calibrator.get_settings()
        print("Calibration settings:")
        print(settings)

    calibrator = GamepadCalibrator(
        on_start=lambda: (
            calibrate_button.disable(),
            controller_select.disable()
        ),
        on_done=on_done
    )

    calibrator.start()


calibrate_button = Button(
    label="Start Calibration",
    width=200,
    height=50,
    font=font,
    callback=start_calibration
)

controller_select = Select(
    label="Controller",
    label_width=150,
    width=400,
    font=font,
    callback=lambda i: set_selected_gamepad(i)
)
controller_select.set_options(gamepad_names, selected_index=0 if gamepad_names else 0)


def set_selected_gamepad(index):
    global selected_gamepad
    selected_gamepad = index


# Set original positions
controller_select.set_position(50, 50)
calibrate_button.set_position(50, 100)


def draw_axis_bar(label, value, min_val, max_val, center_val=None, x=300, y=0, width=400, height=30, font=None):
    # Label
    if font:
        label_surface, label_rect = font.render(label, WHITE)
        label_rect.topleft = (x - 10 - label_rect.width, y + (height - label_rect.height) // 2)
        screen.blit(label_surface, label_rect)

    # Bar background
    pygame.draw.rect(screen, GREY, (x, y, width, height), 1)
    # Bar fill
    fill_ratio = (value - min_val) / (max_val - min_val) if max_val != min_val else 0.5
    fill_px = int(fill_ratio * width)
    pygame.draw.rect(screen, WHITE, (x, y, fill_px, height))
    # Center line
    if center_val is not None:
        center_ratio = (center_val - min_val) / (max_val - min_val) if max_val != min_val else 0.5
        center_px = int(center_ratio * width)
        pygame.draw.line(screen, (200, 200, 0), (x + center_px, y), (x + center_px, y + height), 2)


running = True
while running:
    screen.fill(DARK_GREY)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        calibrate_button.handle_event(event)
        controller_select.handle_event(event)

    controller_select.draw(screen)
    calibrate_button.draw(screen)

    if calibrator:
        with threading.Lock():
            if selected_gamepad < len(gamepads):
                js = gamepads[selected_gamepad]
                axes = [js.get_axis(i) for i in range(js.get_numaxes())]
                calibrator.update(axes)

        if calibrator.state == CalibratorState.COMPLETE:
            settings = calibrator.get_settings()

            def safe_get_axis(axis_idx):
                try:
                    return js.get_axis(axis_idx)
                except (AttributeError, IndexError):
                    return 0.0

            base_x = 150
            bar_width = 500
            bar_y = 180
            bar_spacing = 50

            # Steering
            s = settings["steering"]
            if s["axis"] is not None:
                draw_axis_bar(
                    "Steering", safe_get_axis(s["axis"]),
                    min_val=s["min"], max_val=s["max"], center_val=s["center"],
                    x=base_x, y=bar_y, width=bar_width, font=font
                )
                bar_y += bar_spacing

            # Throttle
            t = settings["throttle"]
            if t["axis"] is not None:
                draw_axis_bar(
                    "Throttle", safe_get_axis(t["axis"]),
                    min_val=t["min"], max_val=t["max"],
                    x=base_x, y=bar_y, width=bar_width, font=font
                )
                bar_y += bar_spacing

            # Brake
            b = settings["brake"]
            if b["axis"] is not None:
                draw_axis_bar(
                    "Brake", safe_get_axis(b["axis"]),
                    min_val=b["min"], max_val=b["max"],
                    x=base_x, y=bar_y, width=bar_width, font=font
                )
        elif calibrator.stage is not None:
            # Show calibration step instructions (only while calibrating)
            steps = calibrator.get_steps()
            for i, (label, active) in enumerate(steps):
                color = WHITE if active else GREY
                label_surface, label_rect = font.render(label, color)
                label_rect.topleft = (50, 180 + i * 40)
                screen.blit(label_surface, label_rect)

    pygame.display.flip()
    clock.tick(30)

pygame.quit()
