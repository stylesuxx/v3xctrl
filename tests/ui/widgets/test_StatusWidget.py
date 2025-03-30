import pytest
import pygame

from ui.widgets.StatusWidget import StatusWidget


@pytest.fixture(scope="module", autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture
def screen():
    return pygame.Surface((200, 100))  # Dummy screen


def test_default_initialization():
    widget = StatusWidget(position=(10, 10), size=20, label="Test")

    assert widget.position == (10, 10)
    assert widget.size == 20
    assert widget.label == "Test"
    assert widget.padding == 8
    assert widget.color == widget.DEFAULT_COLOR


def test_status_colors():
    widget = StatusWidget(position=(0, 0), size=10, label="")

    widget.set_status("waiting")
    assert widget.color == widget.WAITING_COLOR

    widget.set_status("success")
    assert widget.color == widget.SUCCESS_COLOR

    widget.set_status("fail")
    assert widget.color == widget.FAIL_COLOR

    widget.set_status("unknown")
    assert widget.color == widget.DEFAULT_COLOR


def test_draw_does_not_crash(screen):
    widget = StatusWidget(position=(0, 0), size=20, label="DrawTest")
    widget.set_status("success")

    # Should not raise any errors
    widget.draw(screen)

    # Optionally, inspect a pixel from the widget area
    color = screen.get_at((1, 1))
    assert isinstance(color, pygame.Color)
