import pygame

from ui.colors import DARK_GREY
from ui.menu.calibration.GamepadManager import GamepadManager

active_guid = "030003f05e0400008e02000010010000"
calibrations = {
    "030003f05e0400008e02000010010000_": {
        "steering": {"axis": 0, "min": -1.0, "max": 1.0, "center": 0.0},
        "throttle": {"axis": 4, "min": -1.0, "max": 0.0, "center": None, "invert": True},
        "brake": {"axis": 4, "min": 0.0, "max": 1.0, "center": None},
    },
    "030003f05e0400008e02000010010000": {
        "steering": {"axis": 0, "min": -1.0, "max": 1.0, "center": 0.0},
        "throttle": {"axis": 5, "min": -1.0, "max": 1.0, "center": None},
        "brake": {"axis": 2, "min": -1.0, "max": 1.0, "center": None},
    }
}

# Initialize GamepadManager, load known calibrations and set active controller
gamepad_manager = GamepadManager()
for guid, calibration in calibrations.items():
    gamepad_manager.set_calibration(guid, calibration)
gamepad_manager.set_active(active_guid)
gamepad_manager.start()

pygame.init()
size = (1280, 720)
screen = pygame.display.set_mode(size, pygame.DOUBLEBUF | pygame.SCALED)
pygame.display.set_caption("Read inputs")
clock = pygame.time.Clock()

running = True
while running:
    screen.fill(DARK_GREY)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    inputs = gamepad_manager.read_inputs()
    print(inputs)

    pygame.display.flip()
    clock.tick(30)

gamepad_manager.stop()
gamepad_manager.join()

pygame.quit()
