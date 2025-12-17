"""Tests for TimingController - manages timing intervals and frame rates."""
import time
import pytest

from v3xctrl_ui.controllers.TimingController import TimingController
from v3xctrl_ui.core.ApplicationModel import ApplicationModel


class TestTimingControllerInitialization:
    """Test TimingController initialization."""

    def test_initialization_with_default_settings(self):
        """Test that TimingController initializes with default timing values."""
        settings = {
            "timing": {
                "control_update_hz": 30,
                "latency_check_hz": 1,
                "main_loop_fps": 60
            }
        }
        model = ApplicationModel()

        controller = TimingController(settings, model)

        assert controller.settings == settings
        assert controller.model == model
        assert controller.main_loop_fps == 60
        assert model.control_interval == pytest.approx(1.0 / 30, abs=0.001)
        assert model.latency_interval == 1.0

    def test_initialization_with_custom_settings(self):
        """Test that TimingController initializes with custom timing values."""
        settings = {
            "timing": {
                "control_update_hz": 60,
                "latency_check_hz": 5,
                "main_loop_fps": 120
            }
        }
        model = ApplicationModel()

        controller = TimingController(settings, model)

        assert controller.main_loop_fps == 120
        assert model.control_interval == pytest.approx(1.0 / 60, abs=0.001)
        assert model.latency_interval == 0.2

    def test_initialization_with_missing_timing_section(self):
        """Test that TimingController handles missing timing section gracefully."""
        settings = {}
        model = ApplicationModel()

        controller = TimingController(settings, model)

        # Should use defaults
        assert controller.main_loop_fps == 60
        assert model.control_interval == pytest.approx(1.0 / 30, abs=0.001)
        assert model.latency_interval == 1.0

    def test_initialization_with_partial_timing_settings(self):
        """Test that TimingController handles partial timing settings."""
        settings = {
            "timing": {
                "control_update_hz": 90
                # Missing latency_check_hz and main_loop_fps
            }
        }
        model = ApplicationModel()

        controller = TimingController(settings, model)

        assert controller.main_loop_fps == 60  # Default
        assert model.control_interval == pytest.approx(1.0 / 90, abs=0.001)
        assert model.latency_interval == 1.0  # Default


class TestUpdateFromSettings:
    """Test updating timing from settings."""

    def test_update_from_settings(self):
        """Test that update_from_settings recalculates intervals."""
        settings = {
            "timing": {
                "control_update_hz": 30,
                "latency_check_hz": 1,
                "main_loop_fps": 60
            }
        }
        model = ApplicationModel()
        controller = TimingController(settings, model)

        # Change settings
        controller.settings = {
            "timing": {
                "control_update_hz": 120,
                "latency_check_hz": 10,
                "main_loop_fps": 144
            }
        }
        controller.update_from_settings()

        assert controller.main_loop_fps == 144
        assert model.control_interval == pytest.approx(1.0 / 120, abs=0.001)
        assert model.latency_interval == 0.1

    def test_update_from_settings_preserves_model_reference(self):
        """Test that updating settings doesn't break model reference."""
        settings = {"timing": {"control_update_hz": 30}}
        model = ApplicationModel()
        controller = TimingController(settings, model)

        initial_model = controller.model
        controller.update_from_settings()

        assert controller.model is initial_model


class TestShouldUpdateControl:
    """Test control update timing checks."""

    def test_should_update_control_when_enough_time_passed(self):
        """Test that should_update_control returns True when interval elapsed."""
        settings = {
            "timing": {
                "control_update_hz": 30  # 1/30 = 0.0333s interval
            }
        }
        model = ApplicationModel()
        controller = TimingController(settings, model)

        now = time.monotonic()
        model.last_control_update = now - 0.04  # 40ms ago, more than 33ms

        assert controller.should_update_control(now) is True

    def test_should_not_update_control_when_insufficient_time(self):
        """Test that should_update_control returns False when interval not elapsed."""
        settings = {
            "timing": {
                "control_update_hz": 30  # 1/30 = 0.0333s interval
            }
        }
        model = ApplicationModel()
        controller = TimingController(settings, model)

        now = time.monotonic()
        model.last_control_update = now - 0.01  # 10ms ago, less than 33ms

        assert controller.should_update_control(now) is False

    def test_should_update_control_exact_boundary(self):
        """Test boundary condition when time exceeds interval slightly."""
        settings = {
            "timing": {
                "control_update_hz": 30
            }
        }
        model = ApplicationModel()
        controller = TimingController(settings, model)

        now = time.monotonic()
        model.last_control_update = now - (1.0 / 30) - 0.001  # Slightly over interval

        assert controller.should_update_control(now) is True


class TestShouldCheckLatency:
    """Test latency check timing checks."""

    def test_should_check_latency_when_enough_time_passed(self):
        """Test that should_check_latency returns True when interval elapsed."""
        settings = {
            "timing": {
                "latency_check_hz": 1  # 1 second interval
            }
        }
        model = ApplicationModel()
        controller = TimingController(settings, model)

        now = time.monotonic()
        model.last_latency_check = now - 1.1  # 1.1s ago

        assert controller.should_check_latency(now) is True

    def test_should_not_check_latency_when_insufficient_time(self):
        """Test that should_check_latency returns False when interval not elapsed."""
        settings = {
            "timing": {
                "latency_check_hz": 1  # 1 second interval
            }
        }
        model = ApplicationModel()
        controller = TimingController(settings, model)

        now = time.monotonic()
        model.last_latency_check = now - 0.5  # 0.5s ago

        assert controller.should_check_latency(now) is False

    def test_should_check_latency_with_high_frequency(self):
        """Test latency checking with high frequency settings."""
        settings = {
            "timing": {
                "latency_check_hz": 10  # 0.1s interval
            }
        }
        model = ApplicationModel()
        controller = TimingController(settings, model)

        now = time.monotonic()
        model.last_latency_check = now - 0.15  # 150ms ago

        assert controller.should_check_latency(now) is True


class TestMarkTimestamps:
    """Test marking update timestamps."""

    def test_mark_control_updated(self):
        """Test that mark_control_updated sets the timestamp."""
        settings = {"timing": {}}
        model = ApplicationModel()
        controller = TimingController(settings, model)

        now = time.monotonic()
        controller.mark_control_updated(now)

        assert model.last_control_update == now

    def test_mark_latency_checked(self):
        """Test that mark_latency_checked sets the timestamp."""
        settings = {"timing": {}}
        model = ApplicationModel()
        controller = TimingController(settings, model)

        now = time.monotonic()
        controller.mark_latency_checked(now)

        assert model.last_latency_check == now

    def test_mark_updates_independent(self):
        """Test that marking one timestamp doesn't affect the other."""
        settings = {"timing": {}}
        model = ApplicationModel()
        controller = TimingController(settings, model)

        control_time = time.monotonic()
        controller.mark_control_updated(control_time)

        time.sleep(0.01)  # Small delay

        latency_time = time.monotonic()
        controller.mark_latency_checked(latency_time)

        assert model.last_control_update == control_time
        assert model.last_latency_check == latency_time
        assert model.last_control_update != model.last_latency_check


class TestTimingControllerIntegration:
    """Integration tests simulating real usage patterns."""

    def test_typical_update_cycle(self):
        """Test a typical update cycle with control and latency checks."""
        settings = {
            "timing": {
                "control_update_hz": 30,
                "latency_check_hz": 1,
                "main_loop_fps": 60
            }
        }
        model = ApplicationModel()
        controller = TimingController(settings, model)

        # Initialize timestamps
        start = time.monotonic()
        model.last_control_update = start
        model.last_latency_check = start

        # Simulate time passing (40ms, should trigger control update)
        now = start + 0.04

        if controller.should_update_control(now):
            controller.mark_control_updated(now)

        assert model.last_control_update == now

        # Latency check shouldn't trigger yet
        assert controller.should_check_latency(now) is False

    def test_settings_hot_reload(self):
        """Test changing settings during runtime."""
        settings = {
            "timing": {
                "control_update_hz": 30,
                "main_loop_fps": 60
            }
        }
        model = ApplicationModel()
        controller = TimingController(settings, model)

        original_interval = model.control_interval

        # User changes settings in menu
        controller.settings = {
            "timing": {
                "control_update_hz": 60,
                "main_loop_fps": 120
            }
        }
        controller.update_from_settings()

        # Intervals should be updated
        assert model.control_interval != original_interval
        assert model.control_interval == pytest.approx(1.0 / 60, abs=0.001)
        assert controller.main_loop_fps == 120

    def test_multiple_frames_with_timing(self):
        """Test multiple frame updates respecting timing intervals."""
        settings = {
            "timing": {
                "control_update_hz": 10  # Very slow for testing
            }
        }
        model = ApplicationModel()
        controller = TimingController(settings, model)

        start = time.monotonic()
        model.last_control_update = start

        updates_triggered = 0

        # Simulate 5 frames at 60fps (should only trigger 1 update at 10Hz)
        for i in range(5):
            now = start + (i * 0.0166)  # ~60fps intervals
            if controller.should_update_control(now):
                controller.mark_control_updated(now)
                updates_triggered += 1

        # At 10Hz, only the first check should trigger (0.1s interval)
        assert updates_triggered <= 1

    def test_high_frequency_control_updates(self):
        """Test high frequency control updates (120Hz)."""
        settings = {
            "timing": {
                "control_update_hz": 120
            }
        }
        model = ApplicationModel()
        controller = TimingController(settings, model)

        start = time.monotonic()
        model.last_control_update = start

        # After 1/120 seconds, should allow update
        now = start + (1.0 / 120)
        assert controller.should_update_control(now) is True

        controller.mark_control_updated(now)

        # Immediately after, should not allow update
        assert controller.should_update_control(now) is False
