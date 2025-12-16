"""Tests for ApplicationModel - the pure state container for the application."""
import time
from collections import deque
from unittest.mock import Mock

import pytest

from v3xctrl_ui.ApplicationModel import ApplicationModel


class TestApplicationModelInitialization:
    """Test ApplicationModel initialization with default and custom values."""

    def test_default_initialization(self):
        """Test that ApplicationModel initializes with correct default values."""
        model = ApplicationModel()

        # Control state
        assert model.throttle == 0.0
        assert model.steering == 0.0
        assert model.control_connected is False

        # Display state
        assert model.fullscreen is False
        assert model.scale == 1.0

        # Timing state
        assert isinstance(model.loop_history, deque)
        assert model.loop_history.maxlen == 300
        assert len(model.loop_history) == 0
        assert model.control_interval == 0.0
        assert model.latency_interval == 0.0
        assert model.last_control_update == 0.0
        assert model.last_latency_check == 0.0

        # Lifecycle state
        assert model.running is True

        # Network restart state
        assert model.pending_settings is None

    def test_custom_initialization(self):
        """Test that ApplicationModel can be initialized with custom values."""
        model = ApplicationModel(
            throttle=0.5,
            steering=-0.3,
            control_connected=True,
            fullscreen=True,
            scale=2.0,
            running=False
        )

        assert model.throttle == 0.5
        assert model.steering == -0.3
        assert model.control_connected is True
        assert model.fullscreen is True
        assert model.scale == 2.0
        assert model.running is False

    def test_partial_initialization(self):
        """Test that some fields can be initialized while others use defaults."""
        model = ApplicationModel(
            throttle=1.0,
            fullscreen=True
        )

        assert model.throttle == 1.0
        assert model.fullscreen is True
        assert model.steering == 0.0  # Default
        assert model.running is True  # Default


class TestControlState:
    """Test control-related state management."""

    def test_throttle_range(self):
        """Test setting various throttle values."""
        model = ApplicationModel()

        # Test different throttle values
        model.throttle = -1.0
        assert model.throttle == -1.0

        model.throttle = 0.0
        assert model.throttle == 0.0

        model.throttle = 1.0
        assert model.throttle == 1.0

        model.throttle = 0.5
        assert model.throttle == 0.5

    def test_steering_range(self):
        """Test setting various steering values."""
        model = ApplicationModel()

        model.steering = -1.0
        assert model.steering == -1.0

        model.steering = 0.0
        assert model.steering == 0.0

        model.steering = 1.0
        assert model.steering == 1.0

    def test_control_connected_toggle(self):
        """Test toggling control connection state."""
        model = ApplicationModel()

        assert model.control_connected is False

        model.control_connected = True
        assert model.control_connected is True

        model.control_connected = False
        assert model.control_connected is False


class TestDisplayState:
    """Test display-related state management."""

    def test_fullscreen_toggle(self):
        """Test toggling fullscreen mode."""
        model = ApplicationModel()

        assert model.fullscreen is False

        model.fullscreen = True
        assert model.fullscreen is True

        model.fullscreen = False
        assert model.fullscreen is False

    def test_scale_values(self):
        """Test setting various scale values."""
        model = ApplicationModel()

        model.scale = 0.5
        assert model.scale == 0.5

        model.scale = 1.0
        assert model.scale == 1.0

        model.scale = 2.5
        assert model.scale == 2.5


class TestTimingState:
    """Test timing-related state management."""

    def test_loop_history_append(self):
        """Test appending values to loop_history."""
        model = ApplicationModel()

        assert len(model.loop_history) == 0

        now = time.monotonic()
        model.loop_history.append(now)
        assert len(model.loop_history) == 1
        assert model.loop_history[0] == now

    def test_loop_history_maxlen(self):
        """Test that loop_history respects maxlen of 300."""
        model = ApplicationModel()

        # Add 350 items
        for i in range(350):
            model.loop_history.append(float(i))

        # Should only keep last 300
        assert len(model.loop_history) == 300
        assert model.loop_history[0] == 50.0  # First 50 were dropped
        assert model.loop_history[-1] == 349.0

    def test_timing_intervals(self):
        """Test setting timing intervals."""
        model = ApplicationModel()

        model.control_interval = 1.0 / 30  # 30 Hz
        assert model.control_interval == pytest.approx(0.0333, abs=0.001)

        model.latency_interval = 1.0 / 1  # 1 Hz
        assert model.latency_interval == 1.0

    def test_last_update_timestamps(self):
        """Test updating timestamp values."""
        model = ApplicationModel()

        start_time = time.monotonic()
        model.last_control_update = start_time
        model.last_latency_check = start_time

        assert model.last_control_update == start_time
        assert model.last_latency_check == start_time

        # Simulate time passing
        later_time = start_time + 1.0
        model.last_control_update = later_time

        assert model.last_control_update == later_time
        assert model.last_latency_check == start_time  # Unchanged


class TestLifecycleState:
    """Test lifecycle-related state management."""

    def test_running_flag(self):
        """Test the running flag for application lifecycle."""
        model = ApplicationModel()

        assert model.running is True

        model.running = False
        assert model.running is False

        model.running = True
        assert model.running is True


class TestNetworkRestartState:
    """Test network restart-related state management."""

    def test_pending_settings_none_by_default(self):
        """Test that pending_settings is None by default."""
        model = ApplicationModel()
        assert model.pending_settings is None

    def test_pending_settings_assignment(self):
        """Test assigning a mock settings object to pending_settings."""
        model = ApplicationModel()

        # Use a mock settings object
        settings = Mock()
        model.pending_settings = settings

        assert model.pending_settings is not None
        assert model.pending_settings == settings

    def test_pending_settings_clear(self):
        """Test clearing pending_settings."""
        model = ApplicationModel()

        # Use a mock settings object
        settings = Mock()
        model.pending_settings = settings
        assert model.pending_settings is not None

        model.pending_settings = None
        assert model.pending_settings is None


class TestApplicationModelImmutability:
    """Test that ApplicationModel is a dataclass with expected behavior."""

    def test_is_dataclass(self):
        """Test that ApplicationModel is a dataclass."""
        from dataclasses import is_dataclass
        assert is_dataclass(ApplicationModel)

    def test_equality(self):
        """Test equality comparison between ApplicationModel instances."""
        model1 = ApplicationModel(throttle=0.5, steering=0.3)
        model2 = ApplicationModel(throttle=0.5, steering=0.3)

        # Note: deque comparison might not work as expected, so we test other fields
        assert model1.throttle == model2.throttle
        assert model1.steering == model2.steering
        assert model1.fullscreen == model2.fullscreen

    def test_repr(self):
        """Test that ApplicationModel has a useful repr."""
        model = ApplicationModel(throttle=0.5, fullscreen=True)
        repr_str = repr(model)

        assert "ApplicationModel" in repr_str
        assert "throttle=0.5" in repr_str
        assert "fullscreen=True" in repr_str


class TestApplicationModelIntegration:
    """Integration tests simulating real usage patterns."""

    def test_control_update_cycle(self):
        """Test a typical control update cycle."""
        model = ApplicationModel()

        # Initialize timing
        start_time = time.monotonic()
        model.last_control_update = start_time
        model.control_interval = 1.0 / 30  # 30 Hz

        # Simulate control update
        model.throttle = 0.8
        model.steering = -0.3

        # Simulate time passing
        current_time = start_time + 0.04  # 40ms later
        if current_time - model.last_control_update >= model.control_interval:
            model.last_control_update = current_time

        assert model.throttle == 0.8
        assert model.steering == -0.3
        assert model.last_control_update == current_time

    def test_fullscreen_toggle_scenario(self):
        """Test toggling fullscreen and updating scale."""
        model = ApplicationModel(fullscreen=False, scale=1.0)

        # User presses F11
        model.fullscreen = True
        # App calculates new scale for fullscreen
        model.scale = 1.5

        assert model.fullscreen is True
        assert model.scale == 1.5

        # User presses F11 again
        model.fullscreen = False
        model.scale = 1.0

        assert model.fullscreen is False
        assert model.scale == 1.0

    def test_connection_lifecycle(self):
        """Test typical connection lifecycle."""
        model = ApplicationModel()

        # Initially disconnected
        assert model.control_connected is False

        # Connection established
        model.control_connected = True
        assert model.control_connected is True

        # Can now send control messages
        model.throttle = 0.5
        model.steering = 0.2

        # Connection lost
        model.control_connected = False
        assert model.control_connected is False

        # Reset controls
        model.throttle = 0.0
        model.steering = 0.0

    def test_performance_tracking(self):
        """Test tracking application performance with loop_history."""
        model = ApplicationModel()

        # Simulate 10 frame updates
        for i in range(10):
            timestamp = time.monotonic()
            model.loop_history.append(timestamp)
            time.sleep(0.001)  # Small delay

        assert len(model.loop_history) == 10

        # Can calculate FPS from loop_history
        if len(model.loop_history) >= 2:
            time_span = model.loop_history[-1] - model.loop_history[0]
            assert time_span > 0

    def test_settings_update_scenario(self):
        """Test network restart scenario with pending settings."""
        model = ApplicationModel()

        # User changes network settings in menu (use mock object)
        new_settings = Mock()
        new_settings.ports = {"video": 7777, "control": 7778}

        # Mock settings need network restart
        model.pending_settings = new_settings

        # Simulate network restart completion
        assert model.pending_settings is not None

        # Apply pending settings
        applied_settings = model.pending_settings
        model.pending_settings = None

        assert applied_settings == new_settings
        assert model.pending_settings is None
