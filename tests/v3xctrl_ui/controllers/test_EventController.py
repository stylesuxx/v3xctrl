"""Tests for EventController - handles pygame events and menu state."""
from unittest.mock import Mock, MagicMock, call
import pygame
import pytest

from v3xctrl_ui.controllers.EventController import EventController


class TestEventControllerInitialization:
    """Test EventController initialization."""

    def test_initialization_with_callbacks(self):
        """Test that EventController initializes with all required callbacks."""
        on_quit = Mock()
        on_toggle_fullscreen = Mock()
        create_menu = Mock()
        on_menu_exit = Mock()

        controller = EventController(
            on_quit=on_quit,
            on_toggle_fullscreen=on_toggle_fullscreen,
            create_menu=create_menu,
            on_menu_exit=on_menu_exit
        )

        assert controller.on_quit == on_quit
        assert controller.on_toggle_fullscreen == on_toggle_fullscreen
        assert controller.create_menu == create_menu
        assert controller.on_menu_exit == on_menu_exit
        assert controller.menu is None

    def test_menu_starts_as_none(self):
        """Test that menu is None initially."""
        controller = EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=Mock(),
            create_menu=Mock(),
            on_menu_exit=Mock()
        )

        assert controller.menu is None


class TestEventHandling:
    """Test event handling logic."""

    @pytest.fixture
    def controller(self):
        """Create a controller with mock callbacks for testing."""
        return EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=Mock(),
            create_menu=Mock(return_value=Mock(is_loading=False)),
            on_menu_exit=Mock()
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
        """Test that ESC key creates menu when none exists."""
        esc_event = Mock()
        esc_event.type = pygame.KEYDOWN
        esc_event.key = pygame.K_ESCAPE
        mock_pygame.return_value = [esc_event]

        mock_menu = Mock(is_loading=False)
        controller.create_menu.return_value = mock_menu

        result = controller.handle_events()

        controller.create_menu.assert_called_once()
        assert controller.menu == mock_menu
        assert result is True

    def test_handle_escape_key_exits_menu(self, controller, mock_pygame):
        """Test that ESC key exits menu when menu exists and is not loading."""
        # First create the menu
        controller.menu = Mock(is_loading=False)

        esc_event = Mock()
        esc_event.type = pygame.KEYDOWN
        esc_event.key = pygame.K_ESCAPE
        mock_pygame.return_value = [esc_event]

        result = controller.handle_events()

        controller.on_menu_exit.assert_called_once()
        assert result is True

    def test_handle_escape_key_does_nothing_when_menu_loading(self, controller, mock_pygame):
        """Test that ESC key does nothing when menu is loading."""
        controller.menu = Mock(is_loading=True)

        esc_event = Mock()
        esc_event.type = pygame.KEYDOWN
        esc_event.key = pygame.K_ESCAPE
        mock_pygame.return_value = [esc_event]

        result = controller.handle_events()

        controller.on_menu_exit.assert_not_called()
        assert result is True

    def test_handle_f11_key(self, controller, mock_pygame):
        """Test handling F11 key for fullscreen toggle."""
        f11_event = Mock()
        f11_event.type = pygame.KEYDOWN
        f11_event.key = pygame.K_F11
        mock_pygame.return_value = [f11_event]

        result = controller.handle_events()

        controller.on_toggle_fullscreen.assert_called_once()
        assert result is True

    def test_menu_receives_events_when_exists(self, controller, mock_pygame):
        """Test that menu receives events when it exists."""
        controller.menu = Mock(is_loading=False)

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
        """Test that no error occurs when menu is None."""
        event = Mock()
        event.type = pygame.MOUSEMOTION
        mock_pygame.return_value = [event]

        # Should not raise an error
        result = controller.handle_events()
        assert result is True

    def test_multiple_events_in_sequence(self, controller, mock_pygame):
        """Test handling multiple different events in one call."""
        f11_event = Mock()
        f11_event.type = pygame.KEYDOWN
        f11_event.key = pygame.K_F11

        mouse_event = Mock()
        mouse_event.type = pygame.MOUSEMOTION

        mock_pygame.return_value = [f11_event, mouse_event]

        result = controller.handle_events()

        controller.on_toggle_fullscreen.assert_called_once()
        assert result is True


class TestMenuManagement:
    """Test menu management methods."""

    def test_clear_menu(self):
        """Test clearing the menu."""
        controller = EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=Mock(),
            create_menu=Mock(),
            on_menu_exit=Mock()
        )

        controller.menu = Mock()
        assert controller.menu is not None

        controller.clear_menu()
        assert controller.menu is None

    def test_clear_menu_when_already_none(self):
        """Test clearing menu when it's already None."""
        controller = EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=Mock(),
            create_menu=Mock(),
            on_menu_exit=Mock()
        )

        assert controller.menu is None
        controller.clear_menu()  # Should not raise error
        assert controller.menu is None

    def test_set_menu_tab_enabled_when_menu_exists(self):
        """Test enabling/disabling menu tabs when menu exists."""
        controller = EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=Mock(),
            create_menu=Mock(),
            on_menu_exit=Mock()
        )

        mock_menu = Mock()
        controller.menu = mock_menu

        controller.set_menu_tab_enabled("Streamer", True)
        mock_menu.set_tab_enabled.assert_called_once_with("Streamer", True)

    def test_set_menu_tab_enabled_when_menu_is_none(self):
        """Test that set_menu_tab_enabled does nothing when menu is None."""
        controller = EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=Mock(),
            create_menu=Mock(),
            on_menu_exit=Mock()
        )

        assert controller.menu is None
        # Should not raise error
        controller.set_menu_tab_enabled("Streamer", True)


class TestEventControllerIntegration:
    """Integration tests simulating real usage patterns."""

    def test_menu_lifecycle(self, monkeypatch):
        """Test complete menu lifecycle: create, interact, exit."""
        mock_get = Mock(return_value=[])
        monkeypatch.setattr('pygame.event.get', mock_get)

        on_menu_exit = Mock()
        create_menu = Mock(return_value=Mock(is_loading=False))

        controller = EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=Mock(),
            create_menu=create_menu,
            on_menu_exit=on_menu_exit
        )

        # Initially no menu
        assert controller.menu is None

        # Press ESC to create menu
        esc_event = Mock()
        esc_event.type = pygame.KEYDOWN
        esc_event.key = pygame.K_ESCAPE
        mock_get.return_value = [esc_event]

        controller.handle_events()
        assert controller.menu is not None
        create_menu.assert_called_once()

        # Press ESC again to exit menu
        controller.handle_events()
        on_menu_exit.assert_called_once()

    def test_fullscreen_toggle_during_menu(self, monkeypatch):
        """Test that F11 works even when menu is open."""
        mock_get = Mock(return_value=[])
        monkeypatch.setattr('pygame.event.get', mock_get)

        on_toggle_fullscreen = Mock()
        controller = EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=on_toggle_fullscreen,
            create_menu=Mock(return_value=Mock(is_loading=False)),
            on_menu_exit=Mock()
        )

        controller.menu = Mock(is_loading=False)

        # Press F11 while menu is open
        f11_event = Mock()
        f11_event.type = pygame.KEYDOWN
        f11_event.key = pygame.K_F11
        mock_get.return_value = [f11_event]

        controller.handle_events()

        on_toggle_fullscreen.assert_called_once()
        # Menu should still receive the event
        controller.menu.handle_event.assert_called_once_with(f11_event)

    def test_quit_during_menu(self, monkeypatch):
        """Test that quit works even when menu is open."""
        mock_get = Mock(return_value=[])
        monkeypatch.setattr('pygame.event.get', mock_get)

        on_quit = Mock()
        controller = EventController(
            on_quit=on_quit,
            on_toggle_fullscreen=Mock(),
            create_menu=Mock(),
            on_menu_exit=Mock()
        )

        controller.menu = Mock(is_loading=False)

        quit_event = Mock()
        quit_event.type = pygame.QUIT
        mock_get.return_value = [quit_event]

        result = controller.handle_events()

        on_quit.assert_called_once()
        assert result is False

    def test_tab_enable_during_connection_state_change(self):
        """Test enabling streamer tab when connection state changes."""
        controller = EventController(
            on_quit=Mock(),
            on_toggle_fullscreen=Mock(),
            create_menu=Mock(),
            on_menu_exit=Mock()
        )

        # Simulate connection established while menu is open
        mock_menu = Mock()
        controller.menu = mock_menu

        # Enable streamer tab
        controller.set_menu_tab_enabled("Streamer", True)
        mock_menu.set_tab_enabled.assert_called_with("Streamer", True)

        # Simulate connection lost
        controller.set_menu_tab_enabled("Streamer", False)
        mock_menu.set_tab_enabled.assert_called_with("Streamer", False)

        assert mock_menu.set_tab_enabled.call_count == 2
