import pytest
import pygame
from ui.widgets.FpsWidget import FpsWidget


@pytest.fixture(scope="module", autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()

@pytest.fixture
def screen():
    return pygame.Surface((200, 100))  # Dummy screen


def test_draw_with_insufficient_history(screen):
    widget = FpsWidget((0, 0), (100, 50), "FPS")

    widget.draw(screen, [])
    widget.draw(screen, [30])


def test_draw_with_valid_history(screen):
    widget = FpsWidget((0, 0), (100, 50), "FPS")

    history = [30 + (i % 5) for i in range(60)]
    widget.draw(screen, history)
