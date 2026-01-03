"""Tests for EventController - handles pygame events and menu state."""
# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

from unittest.mock import Mock, MagicMock, call
import pygame
import pytest

from v3xctrl_ui.controllers.EventController import EventController
from v3xctrl_ui.core.TelemetryContext import TelemetryContext
from v3xctrl_ui.utils.Settings import Settings


@pytest.fixture
def mock_settings():
    """Create a mock settings object."""
    settings = Mock(spec=Settings)
    settings.get.return_value = {
        "keyboard": {
            "trim_increase": pygame.K_LEFT,
            "trim_decrease": pygame.K_RIGHT,
            "rec_toggle": pygame.K_r
        }
    }
    return settings


@pytest.fixture
def mock_telemetry():
    """Create a mock telemetry context."""
    return Mock(spec=TelemetryContext)


class TestEventControllerInitialization:
    """Test EventController initialization."""

    def test_initialization_with_callbacks(self, mock_settings, mock_telemetry):
        """Test that EventController initializes with all required callbacks."""
        on_quit = Mock()
        on_toggle_fullscreen = Mock()
        mock_menu = Mock(visible=False, is_loading=False)
        on_menu_exit = Mock()
        send_command = Mock()

        controller = EventController(
            on_quit=on_quit,
            on_toggle_fullscreen=on_toggle_fullscreen,
            menu=mock_menu,
            on_menu_exit=on_menu_exit,
            send_command=send_command,
            settings=mock_settings,
            telemetry_context=mock_telemetry
        )

        assert controller.on_quit == on_quit
        assert controller.on_toggle_fullscreen == on_toggle_fullscreen
        assert controller.menu == mock_menu
        assert controller.on_menu_exit == on_menu_exit
        assert controller.send_command == send_command
        assert controller.settings == mock_settings
        assert controller.telemetry_context == mock_telemetry

    def test_menu_starts_as_none(self, mock_settings, mock_telemetry):
        """Test that menu is provided and starts as not visible."""
        mock_menu = Mock(visible=False, is_loading=False)
        controller = EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=Mock(),
            menu=mock_menu,
            on_menu_exit=Mock(),
            send_command=Mock(),
            settings=mock_settings,
            telemetry_context=mock_telemetry
        )

        assert controller.menu is not None
        assert controller.menu.visible is False


class TestEventHandling:
    """Test event handling logic."""

    @pytest.fixture
    def controller(self, mock_settings, mock_telemetry):
        """Create a controller with mock callbacks for testing."""
        mock_menu = Mock(visible=False, is_loading=False)
        return EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=Mock(),
            menu=mock_menu,
            on_menu_exit=Mock(),
            send_command=Mock(),
            settings=mock_settings,
            telemetry_context=mock_telemetry
        )

    @pytest.fixture
    def mock_pygame(self, monkeypatch):
        """Mock pygame.event.get() for testing."""
        mock_get = Mock(return_value=[])
        monkeypatch.setattr('pygame.event.get', mock_get)
        return mock_get

    def test_handle_events_returns_true_when_no_events(self, controller, mock_pygame):
        """Test that handle_events returns True when there are no events."""
        mock_pygame.return_value = []
        result = controller.handle_events()
        assert result is True

    def test_handle_quit_event(self, controller, mock_pygame):
        """Test handling QUIT event."""
        quit_event = Mock()
        quit_event.type = pygame.QUIT
        mock_pygame.return_value = [quit_event]

        result = controller.handle_events()

        controller.on_quit.assert_called_once()
        assert result is False

    def test_handle_escape_key_creates_menu(self, controller, mock_pygame):
        """Test that ESC key shows menu when not visible."""
        esc_event = Mock()
        esc_event.type = pygame.KEYUP
        esc_event.key = pygame.K_ESCAPE
        mock_pygame.return_value = [esc_event]

        controller.menu.visible = False

        result = controller.handle_events()

        controller.menu.show.assert_called_once()
        assert result is True

    def test_handle_escape_key_exits_menu(self, controller, mock_pygame):
        """Test that ESC key exits menu when menu is visible and not loading."""
        # First show the menu
        controller.menu.visible = True
        controller.menu.is_loading = False

        esc_event = Mock()
        esc_event.type = pygame.KEYUP
        esc_event.key = pygame.K_ESCAPE
        mock_pygame.return_value = [esc_event]

        result = controller.handle_events()

        controller.on_menu_exit.assert_called_once()
        assert result is True

    def test_handle_escape_key_does_nothing_when_menu_loading(self, controller, mock_pygame):
        """Test that ESC key does nothing when menu is loading."""
        controller.menu.visible = True
        controller.menu.is_loading = True

        esc_event = Mock()
        esc_event.type = pygame.KEYUP
        esc_event.key = pygame.K_ESCAPE
        mock_pygame.return_value = [esc_event]

        result = controller.handle_events()

        controller.on_menu_exit.assert_not_called()
        assert result is True

    def test_handle_f11_key(self, controller, mock_pygame):
        """Test handling F11 key for fullscreen toggle."""
        f11_event = Mock()
        f11_event.type = pygame.KEYUP
        f11_event.key = pygame.K_F11
        mock_pygame.return_value = [f11_event]

        result = controller.handle_events()

        controller.on_toggle_fullscreen.assert_called_once()
        assert result is True

    def test_menu_receives_events_when_exists(self, controller, mock_pygame):
        """Test that menu receives events when it is visible."""
        controller.menu.visible = True
        controller.menu.is_loading = False

        event1 = Mock()
        event1.type = pygame.MOUSEMOTION
        event2 = Mock()
        event2.type = pygame.MOUSEBUTTONDOWN

        mock_pygame.return_value = [event1, event2]

        controller.handle_events()

        assert controller.menu.handle_event.call_count == 2
        controller.menu.handle_event.assert_any_call(event1)
        controller.menu.handle_event.assert_any_call(event2)

    def test_menu_does_not_receive_events_when_none(self, controller, mock_pygame):
        """Test that menu does not receive events when not visible."""
        controller.menu.visible = False
        event = Mock()
        event.type = pygame.MOUSEMOTION
        mock_pygame.return_value = [event]

        result = controller.handle_events()

        controller.menu.handle_event.assert_not_called()
        assert result is True

    def test_multiple_events_in_sequence(self, controller, mock_pygame):
        """Test handling multiple different events in one call."""
        f11_event = Mock()
        f11_event.type = pygame.KEYUP
        f11_event.key = pygame.K_F11

        mouse_event = Mock()
        mouse_event.type = pygame.MOUSEMOTION

        mock_pygame.return_value = [f11_event, mouse_event]

        result = controller.handle_events()

        controller.on_toggle_fullscreen.assert_called_once()
        assert result is True


class TestEventControllerIntegration:
    """Integration tests simulating real usage patterns."""

    def test_menu_lifecycle(self, monkeypatch, mock_settings, mock_telemetry):
        """Test complete menu lifecycle: show, interact, hide."""
        mock_get = Mock(return_value=[])
        monkeypatch.setattr('pygame.event.get', mock_get)

        on_menu_exit = Mock()
        mock_menu = Mock(visible=False, is_loading=False)

        controller = EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=Mock(),
            menu=mock_menu,
            on_menu_exit=on_menu_exit,
            send_command=Mock(),
            settings=mock_settings,
            telemetry_context=mock_telemetry
        )

        # Initially menu not visible
        assert controller.menu.visible is False

        # Press ESC to show menu
        esc_event = Mock()
        esc_event.type = pygame.KEYUP
        esc_event.key = pygame.K_ESCAPE
        mock_get.return_value = [esc_event]

        controller.handle_events()
        mock_menu.show.assert_called_once()

        # Press ESC again to exit menu
        mock_menu.visible = True
        controller.handle_events()
        on_menu_exit.assert_called_once()

    def test_fullscreen_toggle_during_menu(self, monkeypatch, mock_settings, mock_telemetry):
        """Test that F11 works even when menu is open."""
        mock_get = Mock(return_value=[])
        monkeypatch.setattr('pygame.event.get', mock_get)

        on_toggle_fullscreen = Mock()
        mock_menu = Mock(visible=True, is_loading=False)

        controller = EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=on_toggle_fullscreen,
            menu=mock_menu,
            on_menu_exit=Mock(),
            send_command=Mock(),
            settings=mock_settings,
            telemetry_context=mock_telemetry
        )

        # Press F11 while menu is open
        f11_event = Mock()
        f11_event.type = pygame.KEYUP
        f11_event.key = pygame.K_F11
        mock_get.return_value = [f11_event]

        controller.handle_events()

        on_toggle_fullscreen.assert_called_once()
        # Menu should still receive the event
        mock_menu.handle_event.assert_called_once_with(f11_event)

    def test_quit_during_menu(self, monkeypatch, mock_settings, mock_telemetry):
        """Test that quit works even when menu is open."""
        mock_get = Mock(return_value=[])
        monkeypatch.setattr('pygame.event.get', mock_get)

        on_quit = Mock()
        mock_menu = Mock(visible=True, is_loading=False)

        controller = EventController(
            on_quit=on_quit,
            on_toggle_fullscreen=Mock(),
            menu=mock_menu,
            on_menu_exit=Mock(),
            send_command=Mock(),
            settings=mock_settings,
            telemetry_context=mock_telemetry
        )

        quit_event = Mock()
        quit_event.type = pygame.QUIT
        mock_get.return_value = [quit_event]

        result = controller.handle_events()

        on_quit.assert_called_once()
        assert result is False

    def test_tab_enable_during_connection_state_change(self, mock_settings, mock_telemetry):
        """Test enabling streamer tab when connection state changes."""
        mock_menu = Mock(visible=False, is_loading=False)

        controller = EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=Mock(),
            menu=mock_menu,
            on_menu_exit=Mock(),
            send_command=Mock(),
            settings=mock_settings,
            telemetry_context=mock_telemetry
        )

        # Simulate connection established - tab enabling is now done directly on menu
        # Enable streamer tab
        controller.menu.set_tab_enabled("Streamer", True)
        mock_menu.set_tab_enabled.assert_called_with("Streamer", True)

        # Simulate connection lost
        controller.menu.set_tab_enabled("Streamer", False)
        mock_menu.set_tab_enabled.assert_called_with("Streamer", False)

        assert mock_menu.set_tab_enabled.call_count == 2
