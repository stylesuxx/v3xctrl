import pygame
from pygame.freetype import SysFont

from ui.colors import DARK_GREY
from ui.menu.calibration.GamepadCalibrationWidget import GamepadCalibrationWidget
from ui.menu.calibration.GamepadManager import GamepadManager


# This mocks what will be saved in the config file after a calibration
calibrations = {
    "030003f05e0400008e02000010010000": {
        "steering": {"axis": 0, "min": -1.0, "max": 1.0, "center": 0.0},
        "throttle": {"axis": 4, "min": -1.0, "max": 0.0, "center": None, "invert": True},
        "brake": {"axis": 4, "min": 0.0, "max": 1.0, "center": None},
    }
}


def on_calibration_done(guid: str, settings: dict):
    print(f"\n[CALIBRATION DONE] Joystick GUID: {guid}")
    for axis, data in settings.items():
        print(f"  {axis.capitalize()} Axis:")
        for k, v in data.items():
            print(f"    {k}: {v}")


pygame.init()
size = (1280, 720)
screen = pygame.display.set_mode(size, pygame.DOUBLEBUF | pygame.SCALED)
pygame.display.set_caption("Gamepad Calibration")
clock = pygame.time.Clock()
font = SysFont("Arial", 24)

gamepad_manager = GamepadManager()
for guid, calibration in calibrations.items():
    gamepad_manager.set_calibration(guid, calibration)

calibration_widget = GamepadCalibrationWidget(
    font=font,
    manager=gamepad_manager,
    on_calibration_done=on_calibration_done
)
calibration_widget.set_position(50, 50)

gamepad_manager.start()

running = True
while running:
    screen.fill(DARK_GREY)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        calibration_widget.handle_event(event)

    calibration_widget.draw(screen)

    pygame.display.flip()
    clock.tick(30)

gamepad_manager.stop()
gamepad_manager.join()

pygame.quit()
