# Required before importing pygame, otherwise screen might flicker during tests
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
from unittest.mock import Mock
import pygame

from v3xctrl_ui.menu.input import BaseWidget

from v3xctrl_ui.menu.calibration.GamepadCalibrationWidget import GamepadCalibrationWidget
from v3xctrl_ui.menu.calibration.GamepadCalibrator import GamepadCalibrator
from v3xctrl_ui.menu.calibration.defs import CalibrationStage, CalibratorState


class TestGamepadCalibrationWidgetIntegration(unittest.TestCase):
    """Integration tests for GamepadCalibrationWidget with real calibrator"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Initialize pygame for UI components to work
        pygame.init()
        pygame.freetype.init()

        self.font = pygame.freetype.Font(None, 16)

        # Mock GamepadManager
        self.mock_manager = Mock()
        self.mock_manager.get_gamepads.return_value = {}
        self.mock_manager.get_calibration.return_value = None
        self.mock_manager.read_inputs.return_value = {}
        self.mock_manager.add_observer = Mock()

        # Mock joystick (external pygame dependency)
        self.mock_joystick = Mock()
        self.mock_joystick.get_name.return_value = "Test Controller"
        self.mock_joystick.get_guid.return_value = "test-guid-123"
        self.mock_joystick.get_init.return_value = True
        self.mock_joystick.get_numaxes.return_value = 4
        self.mock_joystick.get_axis.return_value = 0.0

        # Callback mocks
        self.mock_on_start = Mock()
        self.mock_on_done = Mock()

        # Create widget with real UI components
        self.widget = GamepadCalibrationWidget(
            font=self.font,
            manager=self.mock_manager,
            on_calibration_start=self.mock_on_start,
            on_calibration_done=self.mock_on_done
        )

    def test_widget_creates_real_calibrator_with_proper_callbacks(self):
        gamepads = {"test-guid-123": self.mock_joystick}
        self.widget._on_gamepads_changed(gamepads)

        self._click_calibrate_button()

        self.assertIsInstance(self.widget.calibrator, GamepadCalibrator)
        self.assertEqual(self.widget.calibrator.state, CalibratorState.ACTIVE)
        self.assertEqual(self.widget.calibrator.stage, CalibrationStage.STEERING)

        self.mock_on_start.assert_called_once()

    def test_real_calibration_stage_progression(self):
        gamepads = {"test-guid-123": self.mock_joystick}
        self.widget._on_gamepads_changed(gamepads)

        self._click_calibrate_button()
        calibrator = self.widget.calibrator
        dialog = self.widget.dialog

        # Initially dialog should not be visible
        self.assertFalse(getattr(dialog, 'visible', True))

        # Test initial stage
        self.assertEqual(calibrator.stage, CalibrationStage.STEERING)
        self.assertEqual(calibrator.state, CalibratorState.ACTIVE)

        # Simulate steering axis movement and detection
        self._simulate_axis_detection_and_calibration(calibrator, "steering", axis_index=0)

        # Should now be in PAUSE state waiting for user confirmation in dialog
        self.assertEqual(calibrator.state, CalibratorState.PAUSE)
        self.assertEqual(calibrator.pending_stage, CalibrationStage.STEERING_CENTER)

        self.assertTrue(getattr(dialog, 'visible', False))
        self._click_dialog_ok_button()

        self.assertEqual(calibrator.stage, CalibrationStage.STEERING_CENTER)
        self.assertEqual(calibrator.state, CalibratorState.ACTIVE)

    def test_complete_calibration_workflow_integration(self):
        gamepads = {"test-guid-123": self.mock_joystick}
        self.widget._on_gamepads_changed(gamepads)

        self._click_calibrate_button()
        calibrator = self.widget.calibrator

        # Simulate complete calibration workflow
        # 1. Steering detection and range calibration
        self._simulate_axis_detection_and_calibration(calibrator, "steering", axis_index=0)
        self._click_dialog_ok_button()

        # 2. Steering center detection
        self._simulate_steering_center_detection(calibrator)
        self._click_dialog_ok_button()

        # 3. Throttle calibration
        self._simulate_axis_detection_and_calibration(calibrator, "throttle", axis_index=1)
        self._click_dialog_ok_button()

        # 4. Brake calibration (should complete automatically)
        self._simulate_axis_detection_and_calibration(calibrator, "brake", axis_index=2, auto_complete=True)

        # Verify calibration completed
        self.assertEqual(calibrator.state, CalibratorState.COMPLETE)
        self.assertIsNone(calibrator.stage)

        # Verify settings were generated correctly
        settings = calibrator.get_settings()
        self.assertIn("steering", settings)
        self.assertIn("throttle", settings)
        self.assertIn("brake", settings)

        # Verify steering has center, others don't
        self.assertIsNotNone(settings["steering"]["center"])
        self.assertIsNone(settings["throttle"]["center"])
        self.assertIsNone(settings["brake"]["center"])

    def test_calibration_settings_integration_with_manager(self):
        """Test that calibration settings properly integrate with manager"""
        # Set up with gamepad and invert settings
        gamepads = {"test-guid-123": self.mock_joystick}
        self.widget._on_gamepads_changed(gamepads)

        self.widget.invert_axes["steering"] = True
        self.widget.invert_axes["throttle"] = False

        # Create a completed calibrator with settings
        calibrator = GamepadCalibrator()
        calibrator.state = CalibratorState.COMPLETE
        calibrator.axes["steering"].axis = 0
        calibrator.axes["steering"].max_values = [-1.0, 1.0, 0.5, -0.8]
        calibrator.axes["steering"].idle_samples = [0.0, 0.01, -0.01]
        calibrator.axes["throttle"].axis = 1
        calibrator.axes["throttle"].max_values = [0.0, 1.0, 0.8]
        calibrator.axes["brake"].axis = 2
        calibrator.axes["brake"].max_values = [0.0, 1.0, 0.9]

        self.widget.calibrator = calibrator

        self._click_calibrate_button()

        on_done_callback = self.widget.calibrator.on_done
        if on_done_callback:
            on_done_callback()

        self.mock_manager.set_calibration.assert_called()
        call_args = self.mock_manager.set_calibration.call_args[0]
        saved_settings = call_args[1]

        self.assertTrue(saved_settings["steering"]["invert"])
        self.assertFalse(saved_settings["throttle"]["invert"])

    def test_invert_axis_integration_with_real_calibration(self):
        gamepads = {"test-guid-123": self.mock_joystick}
        existing_settings = {
            "steering": {"center": 0.0, "min": -1.0, "max": 1.0, "invert": False},
            "throttle": {"min": -1.0, "max": 1.0, "invert": False},
            "brake": {"min": -1.0, "max": 1.0, "invert": False}
        }

        self.mock_manager.get_calibration.return_value = existing_settings
        self.widget._on_gamepads_changed(gamepads)

        initial_invert = self.widget.invert_axes["steering"]
        self._click_checkbox("steering")

        self.assertEqual(self.widget.invert_axes["steering"], not initial_invert)

        self.mock_manager.set_calibration.assert_called()
        call_args = self.mock_manager.set_calibration.call_args[0]
        updated_settings = call_args[1]
        self.assertEqual(updated_settings["steering"]["invert"], not initial_invert)

    def _simulate_axis_detection_and_calibration(self, calibrator, axis_name, axis_index, auto_complete=False):
        """Helper method to simulate axis detection and calibration"""
        # Set up baseline
        baseline = [0.0] * 4
        calibrator.update(baseline)

        # Simulate axis movement for detection
        moved_axes = baseline.copy()
        moved_axes[axis_index] = 0.5
        for _ in range(GamepadCalibrator.FRAME_CONFIRMATION_COUNT + 1):
            calibrator.update(moved_axes)

        # Simulate range calibration with stable periods
        test_values = [0.0, -1.0, 1.0, 0.5, -0.8, 0.8]
        for value in test_values:
            axes = baseline.copy()
            axes[axis_index] = value
            calibrator.update(axes)

        # Add stable frames at both extremes
        # Stable at max
        max_axes = baseline.copy()
        max_axes[axis_index] = 1.0
        for _ in range(GamepadCalibrator.STABLE_FRAME_COUNT + 1):
            calibrator.update(max_axes)

        # Stable at min
        min_axes = baseline.copy()
        min_axes[axis_index] = -1.0
        for _ in range(GamepadCalibrator.STABLE_FRAME_COUNT + 1):
            calibrator.update(min_axes)

        # If this is the final stage (brake), complete automatically
        if auto_complete and hasattr(calibrator, '_complete'):
            calibrator._complete()

    def _simulate_steering_center_detection(self, calibrator):
        """Helper method to simulate steering center detection"""
        center_axes = [0.0] * 4  # Assuming steering is on axis 0

        # Simulate stable center position
        for _ in range(GamepadCalibrator.STABLE_FRAME_COUNT + GamepadCalibrator.IDLE_SAMPLE_COUNT + 1):
            calibrator.update(center_axes)

    def _click_calibrate_button(self):
        button = self.widget.calibrate_button
        self._click_element_center(button)

    def _click_dialog_ok_button(self):
        dialog = self.widget.dialog
        self._click_element_center(dialog.button)

    def _click_checkbox(self, checkbox_name: str):
        checkbox = self.widget.invert_checkboxes[checkbox_name]
        self._click_element_center(checkbox)

    def _click_element_center(self, element: BaseWidget) -> None:
        x, y = element.x, element.y
        width, height = element.get_size()

        click_x = x + width // 2
        click_y = y + height // 2

        mouse_down_event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {'pos': (click_x, click_y), 'button': 1}
        )

        mouse_up_event = pygame.event.Event(
            pygame.MOUSEBUTTONUP,
            {'pos': (click_x, click_y), 'button': 1}
        )

        self.widget.handle_event(mouse_down_event)
        self.widget.handle_event(mouse_up_event)


if __name__ == '__main__':
    unittest.main()
