"""Tests for ApplicationModel - the pure state container for the application."""
from collections import deque

import pytest

from v3xctrl_ui.core.dataclasses import ApplicationModel


class TestApplicationModel:
    """Test ApplicationModel dataclass.

    Note: This is a simple dataclass with no logic, so we only test
    initialization and basic mutation. Excessive getter/setter tests
    for dataclasses provide no value.
    """

    def test_default_initialization(self):
        """Test that ApplicationModel initializes with correct default values."""
        model = ApplicationModel()

        # Verify key defaults
        assert model.throttle == 0.0
        assert model.steering == 0.0
        assert model.control_connected is False
        assert model.fullscreen is False
        assert model.scale == 1.0
        assert model.running is True
        assert isinstance(model.loop_history, deque)
        assert model.loop_history.maxlen == 300
        assert model.pending_settings is None

    def test_custom_initialization(self):
        """Test that ApplicationModel can be initialized with custom values."""
        model = ApplicationModel(
            throttle=0.5,
            steering=-0.3,
            fullscreen=True,
            scale=2.0,
            running=False
        )

        assert model.throttle == 0.5
        assert model.steering == -0.3
        assert model.fullscreen is True
        assert model.scale == 2.0
        assert model.running is False

    def test_state_mutations(self):
        """Test that model state can be mutated (it's a mutable dataclass)."""
        model = ApplicationModel()

        # Mutate various state fields
        model.throttle = 0.8
        model.steering = -0.5
        model.control_connected = True
        model.fullscreen = True
        model.scale = 1.5

        # Verify mutations stuck
        assert model.throttle == 0.8
        assert model.steering == -0.5
        assert model.control_connected is True
        assert model.fullscreen is True
        assert model.scale == 1.5
