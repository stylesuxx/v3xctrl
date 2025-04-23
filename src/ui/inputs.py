import pygame
from pygame.freetype import SysFont
import threading
import time

from ui.menu.Checkbox import Checkbox
from ui.menu.NumberInput import NumberInput
from ui.menu.Button import Button
from ui.menu.Select import Select
from ui.colors import WHITE, DARK_GREY

pygame.init()

size = (1280, 720)
framerate = 30
title = "V3XCTRL Test UI"
flags = pygame.DOUBLEBUF | pygame.SCALED
screen = pygame.display.set_mode(size, flags)
pygame.display.set_caption(title)
clock = pygame.time.Clock()

# Fonts
font = SysFont("Arial", 20)
mono_font = SysFont("Courier", 20)

# Components
calibration_stage = None
calibration_data = {}
checkbox = Checkbox(
    label="Enable Debug Mode",
    font=font,
    checked=False,
    on_change=lambda checked: print("Checkbox changed to", checked)
)

number_input = NumberInput(
    label="Timeout",
    label_width=120,
    input_width=100,
    min_val=0,
    max_val=9999,
    font=font,
    mono_font=mono_font,
    on_change=lambda val: print("NumberInput changed to", val)
)

graphics_select = Select(
    label="Graphics",
    label_width=120,
    width=200,
    font=font,
    callback=lambda i: print(f"Selected graphics index: {i}")
)
graphics_select.set_options([
    "Low",
    "Medium",
    "High",
    "Ultra",
    "Way too long to be displayed in a single line"
], selected_index=1)

gamepad_select = Select(
    label="Controller",
    label_width=120,
    width=400,
    font=font,
    callback=lambda i: print(f"Selected controller index: {i}")
)

input_mode_select = Select(
    label="Input Mode",
    label_width=120,
    width=400,
    font=font,
    callback=lambda i: print(f"Selected input mode index: {i}")
)
input_mode_select.set_options([
    "Analog steering, analog throttle/brake",
    "Analog steering, buttons for throttle/brake"
])

button = Button(
    label="Submit",
    width=150,
    height=40,
    font=font,
    callback=lambda: print("Button clicked with value:", number_input.get_value())
)

calibrate_button = Button(
    label="Calibrate",
    width=150,
    height=40,
    font=font,
    callback=lambda: start_calibration()
)
calibrate_button.disable()

# Positioning
padding = 50
component_spacing = 45
base_y = padding
components = [checkbox, number_input, graphics_select]
positions = []

# Shared gamepad state
gamepads = []
gamepad_names = []
last_gamepad_names = []
gamepad_lock = threading.Lock()

# Background thread to scan gamepads
def background_scan():
    global gamepads, gamepad_names
    import contextlib
    while running:
        devices = []
        names = []
        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            if not js.get_init():
                with contextlib.suppress(Exception):
                    js.init()
            with contextlib.suppress(Exception):
                js.get_axis(0)
            devices.append(js)
            names.append(js.get_name())
        with gamepad_lock:
            gamepads = devices
            gamepad_names = names
        time.sleep(2.0)

# Initial scan
gamepads = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
for g in gamepads:
    g.init()
gamepad_names = [g.get_name() for g in gamepads]
if gamepad_names:
    calibrate_button.enable()
else:
    calibrate_button.disable()
gamepad_select.set_options(gamepad_names, selected_index=0 if gamepad_names else 0)

# Layout assignment
components.append(calibrate_button)
for comp in components:
    comp.set_position(padding, base_y)
    base_y += component_spacing

gamepad_select.set_position(padding, base_y)
base_y += component_spacing

input_mode_select.set_position(padding, base_y)
base_y += component_spacing

instruction_y = base_y
base_y += component_spacing

calibrate_button.set_position(padding, size[1] - padding - button.rect.height * 2 - 10)
button.set_position(padding, size[1] - padding - button.rect.height)

def start_calibration():
    global calibration_stage, calibration_data
    calibration_data = {}
    calibration_stage = "pause"
    calibration_data['pause_message'] = "Starting calibration..."
    calibration_data['pause_timer'] = pygame.time.get_ticks()
    calibration_data['next_stage'] = "steering_detect"
    calibration_data['steering_baseline'] = None
    calibration_data['steering_detection_count'] = 0
    calibration_data['steering_detection_frames'] = 0
    calibration_data['steering_prev_diff'] = 0.0
    calibration_data['steering_idle_stable'] = 0
    calibration_data['steering_idle_last'] = None
    calibration_data['steering_idle_samples'] = []
    calibration_data['throttle_baseline'] = None
    calibration_data['throttle_detection_frames'] = 0

# Start gamepad scanning thread
running = True
scanner_thread = threading.Thread(target=background_scan, daemon=True)
scanner_thread.start()

# Main loop
while running:
    screen.fill(DARK_GREY)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        checkbox.handle_event(event)
        number_input.handle_event(event)
        graphics_select.handle_event(event)
        button.handle_event(event)
        calibrate_button.handle_event(event)

        with gamepad_lock:
            if gamepad_names:
                gamepad_select.handle_event(event)
                if gamepad_select.selected_index < len(gamepad_names):
                    input_mode_select.handle_event(event)

    with gamepad_lock:
        if gamepad_names != last_gamepad_names:
            gamepad_select.set_options(gamepad_names, selected_index=0 if gamepad_names else 0)
            last_gamepad_names = list(gamepad_names)
            if gamepad_names:
                calibrate_button.enable()
            else:
                calibrate_button.disable()

    checkbox.draw(screen)
    number_input.draw(screen)
    button.draw(screen)
    calibrate_button.draw(screen)

    with gamepad_lock:
        draw_input_mode = False
        if gamepad_names:
            gamepad_select.draw(screen)
            if gamepad_select.selected_index < len(gamepad_names):
                draw_input_mode = True
        else:
            label_surface, label_rect = font.render("Please connect a joystick, gamepad or wheel.", WHITE)
            label_rect.topleft = (padding, base_y)
            screen.blit(label_surface, label_rect)

    graphics_select.draw(screen)
    if draw_input_mode:
        input_mode_select.draw(screen)

    if calibration_stage:
        instruction_text = {
            "steering_detect": "Move the steering axis left/right...",
            "steering_max": "Move steering to full left/right to capture range...",
            "steering_center": "Let go of steering to detect center position...",
            "throttle_detect": "Move the throttle axis...",
            "pause": calibration_data.get('pause_message', "Get ready...")
        }.get(calibration_stage, "Calibrating...")

        label_surface, label_rect = font.render(instruction_text, WHITE)
        label_rect.topleft = (padding, instruction_y)
        screen.blit(label_surface, label_rect)

    pygame.display.flip()

    if calibration_stage is not None and gamepads and gamepad_select.selected_index < len(gamepads):
        js = gamepads[gamepad_select.selected_index]
        axes = [js.get_axis(i) for i in range(js.get_numaxes())]

        if calibration_stage == "pause":
            if pygame.time.get_ticks() - calibration_data.get('pause_timer', 0) > 3000:
                calibration_stage = calibration_data.get('next_stage')

        elif calibration_stage == "steering_detect":
            if calibration_data['steering_baseline'] is None:
                calibration_data['steering_baseline'] = axes.copy()
            else:
                diffs = [abs(a - b) for a, b in zip(axes, calibration_data['steering_baseline'])]
                axis = max(range(len(diffs)), key=lambda i: diffs[i])
                diff = diffs[axis]

                if diff > 0.3:
                    calibration_data['steering_detection_frames'] += 1
                    if calibration_data['steering_detection_frames'] >= 15:
                        calibration_data['steering_axis'] = axis
                        print(f"Steering axis identified: {axis}")
                        calibration_stage = "pause"
                        calibration_data['pause_message'] = "Next: Move stick to the extremes..."
                        calibration_data['pause_timer'] = pygame.time.get_ticks()
                        calibration_data['next_stage'] = "steering_max"
                else:
                    calibration_data['steering_detection_frames'] = 0

        elif calibration_stage == "steering_max":
            axis = calibration_data['steering_axis']
            values = calibration_data.setdefault('steering_max_values', [])
            values.append(axes[axis])
            current_max = max(values)
            if 'steering_max_last' not in calibration_data:
                calibration_data['steering_max_last'] = current_max
                calibration_data['steering_max_stable'] = 0
            if current_max > calibration_data['steering_max_last'] + 0.01:
                calibration_data['steering_max_last'] = current_max
                calibration_data['steering_max_stable'] = 0
            else:
                calibration_data['steering_max_stable'] += 1

            if calibration_data['steering_max_stable'] >= 60:
                print(f"Steering axis min/max: {min(values):.2f}/{max(values):.2f}")
                calibration_stage = "pause"
                calibration_data['pause_message'] = "Next: Let go of the stick to detect center..."
                calibration_data['pause_timer'] = pygame.time.get_ticks()
                calibration_data['next_stage'] = "steering_center"

        elif calibration_stage == "steering_center":
            axis = calibration_data['steering_axis']
            value = axes[axis]

            last_value = calibration_data['steering_idle_last']
            if last_value is None:
                calibration_data['steering_idle_last'] = value
            else:
                if abs(value - last_value) < 0.05:
                    calibration_data['steering_idle_stable'] += 1
                    if calibration_data['steering_idle_stable'] >= 60:
                        calibration_data['steering_idle_samples'].append(value)
                        if len(calibration_data['steering_idle_samples']) >= 10:
                            avg = sum(calibration_data['steering_idle_samples']) / len(calibration_data['steering_idle_samples'])
                            print(f"Steering axis idle: {avg:.2f}")
                            calibration_stage = "pause"
                            calibration_data['pause_message'] = "Next: Detect throttle axis..."
                            calibration_data['pause_timer'] = pygame.time.get_ticks()
                            calibration_data['next_stage'] = "throttle_detect"
                else:
                    calibration_data['steering_idle_stable'] = 0
                calibration_data['steering_idle_last'] = value

        elif calibration_stage == "throttle_detect":
            if calibration_data['throttle_baseline'] is None:
                calibration_data['throttle_baseline'] = axes.copy()
            else:
                diffs = [abs(a - b) if i != calibration_data['steering_axis'] else 0 for i, (a, b) in enumerate(zip(axes, calibration_data['throttle_baseline']))]
                axis = max(range(len(diffs)), key=lambda i: diffs[i])
                diff = diffs[axis]

                if diff > 0.3:
                    calibration_data['throttle_detection_frames'] += 1
                    if calibration_data['throttle_detection_frames'] >= 15:
                        calibration_data['throttle_axis'] = axis
                        print(f"Throttle axis identified: {axis}")
                        # calibration_stage = "pause"
                        # calibration_data['pause_message'] = "Next: Move throttle to full..."
                        # calibration_data['pause_timer'] = pygame.time.get_ticks()
                        # calibration_data['next_stage'] = "throttle_max"
                else:
                    calibration_data['throttle_detection_frames'] = 0

    clock.tick(framerate)

pygame.quit()
running = False