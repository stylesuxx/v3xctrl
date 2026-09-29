"""Tests for TimingController - manages timing intervals and frame rates."""

import time

import pytest

from tests.v3xctrl_ui.settings_helper import build_settings
from v3xctrl_ui.core.controllers.TimingController import TimingController
from v3xctrl_ui.core.dataclasses import ApplicationModel


class TestTimingControllerInitialization:
    """Test TimingController initialization."""

    def test_initialization_with_default_settings(self):
        """Test that TimingController initializes with default timing values."""
        settings = build_settings(timing={"control_update_hz": 30, "latency_check_hz": 1, "main_loop_fps": 60})
        model = ApplicationModel()

        controller = TimingController(settings, model)

        assert controller.settings == settings
        assert controller.model == model
        assert controller.main_loop_fps == 60
        assert model.control_interval == pytest.approx(1.0 / 30, abs=0.001)
        assert model.latency_interval == 1.0

    def test_initialization_with_custom_settings(self):
        """Test that TimingController initializes with custom timing values."""
        settings = build_settings(timing={"control_update_hz": 60, "latency_check_hz": 5, "main_loop_fps": 120})
        model = ApplicationModel()

        controller = TimingController(settings, model)

        assert controller.main_loop_fps == 120
        assert model.control_interval == pytest.approx(1.0 / 60, abs=0.001)
        assert model.latency_interval == 0.2

    def test_initialization_with_missing_timing_section(self):
        """Test that TimingController handles missing timing section gracefully."""
        settings = build_settings()
        model = ApplicationModel()

        controller = TimingController(settings, model)

        # Should use defaults
        assert controller.main_loop_fps == 60
        assert model.control_interval == pytest.approx(1.0 / 30, abs=0.001)
        assert model.latency_interval == 1.0

    def test_initialization_with_partial_timing_settings(self):
        """Test that TimingController handles partial timing settings."""
        settings = build_settings(
            timing={
                "control_update_hz": 90
                # Missing latency_check_hz and main_loop_fps
            }
        )
        model = ApplicationModel()

        controller = TimingController(settings, model)

        assert controller.main_loop_fps == 60  # Default
        assert model.control_interval == pytest.approx(1.0 / 90, abs=0.001)
        assert model.latency_interval == 1.0  # Default


class TestUpdateFromSettings:
    """Test updating timing from settings."""

    def test_update_from_settings(self):
        """Test that update_from_settings recalculates intervals."""
        settings = build_settings(timing={"control_update_hz": 30, "latency_check_hz": 1, "main_loop_fps": 60})
        model = ApplicationModel()
        controller = TimingController(settings, model)

        # Change settings
        controller.settings = build_settings(
            timing={"control_update_hz": 120, "latency_check_hz": 10, "main_loop_fps": 144}
        )
        controller.update_from_settings()

        assert controller.main_loop_fps == 144
        assert model.control_interval == pytest.approx(1.0 / 120, abs=0.001)
        assert model.latency_interval == 0.1

    def test_update_from_settings_preserves_model_reference(self):
        """Test that updating settings doesn't break model reference."""
        settings = build_settings(timing={"control_update_hz": 30})
        model = ApplicationModel()
        controller = TimingController(settings, model)

        initial_model = controller.model
        controller.update_from_settings()

        assert controller.model is initial_model


class TestShouldUpdateControl:
    """Test control update timing checks."""


class TestShouldCheckLatency:
    """Test latency check timing checks."""

    def test_should_check_latency_when_enough_time_passed(self):
        """Test that should_check_latency returns True when interval elapsed."""
        settings = build_settings(
            timing={
                "latency_check_hz": 1  # 1 second interval
            }
        )
        model = ApplicationModel()
        controller = TimingController(settings, model)

        now = time.monotonic()
        model.last_latency_check = now - 1.1  # 1.1s ago

        assert controller.should_check_latency(now) is True

    def test_should_not_check_latency_when_insufficient_time(self):
        """Test that should_check_latency returns False when interval not elapsed."""
        settings = build_settings(
            timing={
                "latency_check_hz": 1  # 1 second interval
            }
        )
        model = ApplicationModel()
        controller = TimingController(settings, model)

        now = time.monotonic()
        model.last_latency_check = now - 0.5  # 0.5s ago

        assert controller.should_check_latency(now) is False

    def test_should_check_latency_with_high_frequency(self):
        """Test latency checking with high frequency settings."""
        settings = build_settings(
            timing={
                "latency_check_hz": 10  # 0.1s interval
            }
        )
        model = ApplicationModel()
        controller = TimingController(settings, model)

        now = time.monotonic()
        model.last_latency_check = now - 0.15  # 150ms ago

        assert controller.should_check_latency(now) is True


class TestMarkTimestamps:
    """Test marking update timestamps."""

    def test_mark_latency_checked(self):
        """Test that mark_latency_checked sets the timestamp."""
        settings = build_settings(timing={})
        model = ApplicationModel()
        controller = TimingController(settings, model)

        now = time.monotonic()
        controller.mark_latency_checked(now)

        assert model.last_latency_check == now


class TestTimingControllerIntegration:
    """Integration tests simulating real usage patterns."""

    def test_settings_hot_reload(self):
        """Test changing settings during runtime."""
        settings = build_settings(timing={"control_update_hz": 30, "main_loop_fps": 60})
        model = ApplicationModel()
        controller = TimingController(settings, model)

        original_interval = model.control_interval

        # User changes settings in menu
        controller.settings = build_settings(timing={"control_update_hz": 60, "main_loop_fps": 120})
        controller.update_from_settings()

        # Intervals should be updated
        assert model.control_interval != original_interval
        assert model.control_interval == pytest.approx(1.0 / 60, abs=0.001)
        assert controller.main_loop_fps == 120
