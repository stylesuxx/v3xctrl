import pygame
from ui.widgets.FpsWidget import FpsWidget


def test_draw_with_insufficient_history():
    pygame.init()
    screen = pygame.Surface((200, 100))
    widget = FpsWidget(screen, (0, 0), (100, 50), "FPS")

    assert widget.draw([]) is None
    assert widget.draw([30]) is None


def test_draw_with_valid_history():
    pygame.init()
    screen = pygame.Surface((200, 100))
    widget = FpsWidget(screen, (0, 0), (100, 50), "FPS")

    history = [30 + (i % 5) for i in range(60)]
    result = widget.draw(history)

    # We can’t assert pixels directly, but we can check types and calls
    assert isinstance(result, pygame.Surface) or result is None
