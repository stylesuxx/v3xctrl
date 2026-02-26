import pygame

from v3xctrl_ui.utils.colors import DARK_GREY, WHITE

pygame.init()

# Discover connected gamepads and pick one
pygame.joystick.init()
count = pygame.joystick.get_count()
if count == 0:
    print("No gamepads connected.")
    pygame.quit()
    exit(1)

print(f"Found {count} gamepad(s):")
gamepads = []
for i in range(count):
    js = pygame.joystick.Joystick(i)
    js.init()
    gamepads.append(js)
    print(f"  [{i}] {js.get_name()} (GUID: {js.get_guid()})")

if count == 1:
    js = gamepads[0]
    print(f"\nUsing only available gamepad: {js.get_name()}")
else:
    choice = input(f"\nSelect gamepad [0-{count - 1}]: ")
    js = gamepads[int(choice)]
    print(f"Using gamepad: {js.get_name()}")

size = (1280, 720)
screen = pygame.display.set_mode(size, pygame.DOUBLEBUF | pygame.SCALED)
pygame.display.set_caption("Read inputs")
clock = pygame.time.Clock()
font = pygame.font.SysFont("monospace", 20)

BAR_WIDTH = 200
BAR_HEIGHT = 16
MARGIN_X = 40
MARGIN_Y = 30

running = True
while running:
    screen.fill(DARK_GREY)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            break

    if not running:
        break

    y = MARGIN_Y

    # Header
    header = font.render(f"{js.get_name()}  (GUID: {js.get_guid()})", True, WHITE)
    screen.blit(header, (MARGIN_X, y))
    y += 40

    # Axes
    for a in range(js.get_numaxes()):
        val = js.get_axis(a)
        label = font.render(f"Axis {a}: {val:+.3f}", True, WHITE)
        screen.blit(label, (MARGIN_X, y))

        bar_x = MARGIN_X + 220
        bar_rect = pygame.Rect(bar_x, y + 2, BAR_WIDTH, BAR_HEIGHT)
        pygame.draw.rect(screen, (50, 50, 50), bar_rect)

        fill_w = int((val + 1) / 2 * BAR_WIDTH)
        fill_rect = pygame.Rect(bar_x, y + 2, fill_w, BAR_HEIGHT)
        pygame.draw.rect(screen, (0, 180, 255), fill_rect)

        # Center marker
        center_x = bar_x + BAR_WIDTH // 2
        pygame.draw.line(screen, WHITE, (center_x, y + 2), (center_x, y + 2 + BAR_HEIGHT), 1)

        y += 26

    y += 30

    # Buttons
    btn_label = font.render("Buttons:", True, WHITE)
    screen.blit(btn_label, (MARGIN_X, y))
    y += 28
    bx = MARGIN_X
    for b in range(js.get_numbuttons()):
        pressed = js.get_button(b)
        color = (0, 200, 80) if pressed else (80, 80, 80)
        pygame.draw.circle(screen, color, (bx + 12, y + 10), 10)
        num = font.render(str(b), True, WHITE)
        screen.blit(num, (bx + 4, y + 22))
        bx += 32
        if (b + 1) % 20 == 0:
            bx = MARGIN_X
            y += 50

    y += 60

    # Hats
    hat_label = font.render("Hats:", True, WHITE)
    screen.blit(hat_label, (MARGIN_X, y))
    y += 28
    for h in range(js.get_numhats()):
        hx, hy = js.get_hat(h)
        val_label = font.render(f"Hat {h}: ({hx:+d}, {hy:+d})", True, WHITE)
        screen.blit(val_label, (MARGIN_X, y))
        y += 26

    pygame.display.flip()
    clock.tick(30)

pygame.quit()
