"""Tests for SettingsManager - handles settings updates and coordination."""
import threading
import time
from unittest.mock import Mock

from v3xctrl_ui.SettingsManager import SettingsManager
from v3xctrl_ui.ApplicationModel import ApplicationModel


class TestSettingsManagerInitialization:
    """Test SettingsManager initialization."""

    def test_initialization_with_settings(self):
        """Test that SettingsManager initializes with settings and model."""
        settings = {"video": {"fullscreen": False}, "ports": {"video": 6666}}
        model = ApplicationModel()

        manager = SettingsManager(settings, model)

        assert manager.settings == settings
        assert manager.model == model
        assert manager.old_settings == settings
        assert manager.old_settings is not settings  # Should be a deep copy
        assert manager.network_restart_thread is None
        assert not manager.network_restart_complete.is_set()

    def test_callbacks_initialized_to_none(self):
        """Test that all callbacks are None by default."""
        settings = {}
        model = ApplicationModel()

        manager = SettingsManager(settings, model)

        assert manager.on_timing_update is None
        assert manager.on_network_update is None
        assert manager.on_input_update is None
        assert manager.on_osd_update is None
        assert manager.on_renderer_update is None
        assert manager.on_display_update is None
        assert manager.create_network_restart_thread is None


class TestUpdateSettings:
    """Test settings update logic."""

    def test_update_settings_without_network_restart(self):
        """Test updating settings that don't require network restart."""
        old_settings = {
            "video": {"fullscreen": False},
            "ports": {"video": 6666},
            "relay": {}
        }
        new_settings = {
            "video": {"fullscreen": True},
            "ports": {"video": 6666},  # Same ports
            "relay": {}  # Same relay
        }
        model = ApplicationModel()
        manager = SettingsManager(old_settings, model)

        # Setup callbacks
        display_callback = Mock()
        timing_callback = Mock()
        manager.on_display_update = display_callback
        manager.on_timing_update = timing_callback

        result = manager.update_settings(new_settings)

        assert result is True  # Settings applied immediately
        display_callback.assert_called_once_with(True)
        timing_callback.assert_called_once_with(new_settings)

    def test_update_settings_with_ports_change(self):
        """Test updating settings when ports change (requires restart)."""
        old_settings = {
            "video": {"fullscreen": False},
            "ports": {"video": 6666},
            "relay": {}
        }
        new_settings = {
            "video": {"fullscreen": False},
            "ports": {"video": 7777},  # Changed port
            "relay": {}
        }
        model = ApplicationModel()
        manager = SettingsManager(old_settings, model)

        # Setup restart thread factory
        restart_thread = Mock(spec=threading.Thread)
        manager.create_network_restart_thread = Mock(return_value=restart_thread)

        result = manager.update_settings(new_settings)

        assert result is False  # Network restart needed
        assert model.pending_settings == new_settings
        manager.create_network_restart_thread.assert_called_once_with(new_settings)
        restart_thread.start.assert_called_once()

    def test_update_settings_with_relay_change(self):
        """Test updating settings when relay config changes (requires restart)."""
        old_settings = {
            "video": {"fullscreen": False},
            "ports": {"video": 6666},
            "relay": {"enabled": False}
        }
        new_settings = {
            "video": {"fullscreen": False},
            "ports": {"video": 6666},
            "relay": {"enabled": True}  # Changed relay
        }
        model = ApplicationModel()
        manager = SettingsManager(old_settings, model)

        restart_thread = Mock(spec=threading.Thread)
        manager.create_network_restart_thread = Mock(return_value=restart_thread)

        result = manager.update_settings(new_settings)

        assert result is False
        assert model.pending_settings == new_settings


class TestSettingsEqual:
    """Test settings comparison logic."""

    def test_settings_equal_when_identical(self):
        """Test that identical settings sections are considered equal."""
        settings = {
            "ports": {"video": 6666, "control": 6668}
        }
        model = ApplicationModel()
        manager = SettingsManager(settings, model)

        assert manager.settings_equal(settings, "ports") is True

    def test_settings_not_equal_when_values_differ(self):
        """Test that different values are detected."""
        old_settings = {
            "ports": {"video": 6666, "control": 6668}
        }
        new_settings = {
            "ports": {"video": 7777, "control": 6668}
        }
        model = ApplicationModel()
        manager = SettingsManager(old_settings, model)

        assert manager.settings_equal(new_settings, "ports") is False

    def test_settings_not_equal_when_keys_differ(self):
        """Test that different keys are detected."""
        old_settings = {
            "ports": {"video": 6666}
        }
        new_settings = {
            "ports": {"video": 6666, "control": 6668}
        }
        model = ApplicationModel()
        manager = SettingsManager(old_settings, model)

        assert manager.settings_equal(new_settings, "ports") is False


class TestApplySettings:
    """Test settings application to components."""

    def test_apply_settings_calls_all_callbacks(self):
        """Test that apply_settings calls all registered callbacks."""
        old_settings = {"key": "old"}
        new_settings = {"key": "new"}
        model = ApplicationModel()
        manager = SettingsManager(old_settings, model)

        # Setup all callbacks
        timing_cb = Mock()
        network_cb = Mock()
        input_cb = Mock()
        osd_cb = Mock()
        renderer_cb = Mock()

        manager.on_timing_update = timing_cb
        manager.on_network_update = network_cb
        manager.on_input_update = input_cb
        manager.on_osd_update = osd_cb
        manager.on_renderer_update = renderer_cb

        manager.apply_settings(new_settings)

        # Verify all callbacks were called
        timing_cb.assert_called_once_with(new_settings)
        network_cb.assert_called_once_with(new_settings)
        input_cb.assert_called_once_with(new_settings)
        osd_cb.assert_called_once_with(new_settings)
        renderer_cb.assert_called_once_with(new_settings)

    def test_apply_settings_updates_settings_references(self):
        """Test that apply_settings updates settings and old_settings."""
        old_settings = {"key": "old"}
        new_settings = {"key": "new"}
        model = ApplicationModel()
        manager = SettingsManager(old_settings, model)

        manager.apply_settings(new_settings)

        assert manager.settings == new_settings
        assert manager.old_settings == new_settings
        assert manager.old_settings is not new_settings  # Deep copy

    def test_apply_settings_with_no_callbacks(self):
        """Test that apply_settings works even with no callbacks set."""
        old_settings = {}
        new_settings = {}
        model = ApplicationModel()
        manager = SettingsManager(old_settings, model)

        # Should not raise an error
        manager.apply_settings(new_settings)

        assert manager.settings == new_settings


class TestNetworkRestartCoordination:
    """Test network restart coordination logic."""

    def test_check_network_restart_complete_when_not_set(self):
        """Test that check returns False when restart not complete."""
        settings = {}
        model = ApplicationModel()
        manager = SettingsManager(settings, model)

        result = manager.check_network_restart_complete()

        assert result is False

    def test_check_network_restart_complete_applies_pending_settings(self):
        """Test that pending settings are applied after restart completes."""
        old_settings = {"key": "old"}
        pending_settings = {"key": "pending"}
        model = ApplicationModel()
        manager = SettingsManager(old_settings, model)

        # Set up pending settings
        model.pending_settings = pending_settings
        manager.network_restart_complete.set()

        # Setup callbacks to verify they're called
        timing_cb = Mock()
        manager.on_timing_update = timing_cb

        result = manager.check_network_restart_complete()

        assert result is True
        assert model.pending_settings is None
        assert manager.settings == pending_settings
        timing_cb.assert_called_once_with(pending_settings)

    def test_check_network_restart_complete_clears_event(self):
        """Test that the event is cleared after processing."""
        settings = {}
        model = ApplicationModel()
        manager = SettingsManager(settings, model)

        manager.network_restart_complete.set()
        manager.check_network_restart_complete()

        assert not manager.network_restart_complete.is_set()

    def test_wait_for_network_restart_with_no_thread(self):
        """Test waiting when there's no restart thread."""
        settings = {}
        model = ApplicationModel()
        manager = SettingsManager(settings, model)

        result = manager.wait_for_network_restart()

        assert result is True  # No thread, nothing to wait for

    def test_wait_for_network_restart_with_completed_thread(self):
        """Test waiting for already completed thread."""
        settings = {}
        model = ApplicationModel()
        manager = SettingsManager(settings, model)

        # Create a finished thread
        def dummy_func():
            pass

        thread = threading.Thread(target=dummy_func)
        thread.start()
        thread.join()  # Wait for it to finish

        manager.network_restart_thread = thread

        result = manager.wait_for_network_restart()

        assert result is True


class TestDisplayUpdates:
    """Test display/fullscreen update handling."""

    def test_fullscreen_change_triggers_callback(self):
        """Test that fullscreen changes trigger the display callback."""
        old_settings = {"video": {"fullscreen": False}, "ports": {}, "relay": {}}
        new_settings = {"video": {"fullscreen": True}, "ports": {}, "relay": {}}
        model = ApplicationModel(fullscreen=False)
        manager = SettingsManager(old_settings, model)

        display_cb = Mock()
        manager.on_display_update = display_cb

        manager.update_settings(new_settings)

        display_cb.assert_called_once_with(True)

    def test_no_fullscreen_change_no_callback(self):
        """Test that no callback is triggered when fullscreen doesn't change."""
        old_settings = {"video": {"fullscreen": False}, "ports": {}, "relay": {}}
        new_settings = {"video": {"fullscreen": False}, "ports": {}, "relay": {}}
        model = ApplicationModel(fullscreen=False)
        manager = SettingsManager(old_settings, model)

        display_cb = Mock()
        manager.on_display_update = display_cb

        manager.update_settings(new_settings)

        display_cb.assert_not_called()


class TestSettingsManagerIntegration:
    """Integration tests simulating real usage patterns."""

    def test_settings_update_workflow(self):
        """Test complete settings update workflow."""
        initial_settings = {
            "video": {"fullscreen": False},
            "ports": {"video": 6666},
            "relay": {},
            "timing": {"control_update_hz": 30}
        }
        model = ApplicationModel()
        manager = SettingsManager(initial_settings, model)

        # Setup callbacks
        callbacks_called = []

        def timing_cb(settings):
            callbacks_called.append("timing")

        def input_cb(settings):
            callbacks_called.append("input")

        manager.on_timing_update = timing_cb
        manager.on_input_update = input_cb

        # Update to new settings (no restart needed)
        new_settings = {
            "video": {"fullscreen": True},
            "ports": {"video": 6666},
            "relay": {},
            "timing": {"control_update_hz": 60}
        }

        manager.update_settings(new_settings)

        assert manager.settings == new_settings
        assert "timing" in callbacks_called
        assert "input" in callbacks_called

    def test_network_restart_workflow(self):
        """Test network restart workflow."""
        initial_settings = {
            "ports": {"video": 6666}
        }
        model = ApplicationModel()
        manager = SettingsManager(initial_settings, model)

        # Simulate restart thread
        restart_complete = threading.Event()

        def restart_thread_func(settings):
            time.sleep(0.01)  # Simulate work
            restart_complete.set()
            manager.network_restart_complete.set()

        def create_restart_thread(settings):
            return threading.Thread(target=restart_thread_func, args=(settings,))

        manager.create_network_restart_thread = create_restart_thread

        # Change ports (requires restart)
        new_settings = {"ports": {"video": 7777}}
        result = manager.update_settings(new_settings)

        assert result is False  # Restart needed
        assert model.pending_settings == new_settings

        # Wait for restart to complete
        restart_complete.wait(timeout=1.0)

        # Check restart completion
        result = manager.check_network_restart_complete()

        assert result is True
        assert manager.settings == new_settings
        assert model.pending_settings is None
