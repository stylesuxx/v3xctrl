import unittest
from unittest.mock import MagicMock, patch
from typing import List, Dict, Optional

from v3xctrl_ui.menu.calibration.GamepadCalibrator import GamepadCalibrator
from v3xctrl_ui.menu.calibration.defs import CalibrationStage, CalibratorState, AxisCalibrationData
from v3xctrl_ui.menu.DialogBox import DialogBox


class TestGamepadCalibrator(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.mock_on_start = MagicMock()
        self.mock_on_done = MagicMock()
        self.mock_dialog = MagicMock(spec=DialogBox)

        self.calibrator = GamepadCalibrator(
            on_start=self.mock_on_start,
            on_done=self.mock_on_done,
            dialog=self.mock_dialog
        )

    def test_initialization(self):
        """Test GamepadCalibrator initialization"""
        # Test callbacks are set
        self.assertEqual(self.calibrator.on_start, self.mock_on_start)
        self.assertEqual(self.calibrator.on_done, self.mock_on_done)
        self.assertEqual(self.calibrator.dialog, self.mock_dialog)

        # Test initial state
        self.assertIsNone(self.calibrator.stage)
        self.assertEqual(self.calibrator.state, CalibratorState.PAUSE)
        self.assertIsNone(self.calibrator.pending_stage)
        self.assertFalse(self.calibrator.waiting_for_user)

        # Test axes initialization
        self.assertIn("steering", self.calibrator.axes)
        self.assertIn("throttle", self.calibrator.axes)
        self.assertIn("brake", self.calibrator.axes)

        for axis_name in ["steering", "throttle", "brake"]:
            axis_data = self.calibrator.axes[axis_name]
            self.assertIsInstance(axis_data, AxisCalibrationData)

    def test_initialization_without_callbacks(self):
        """Test initialization without optional parameters"""
        calibrator = GamepadCalibrator()

        self.assertIsNone(calibrator.on_start)
        self.assertIsNone(calibrator.on_done)
        self.assertIsNone(calibrator.dialog)

    def test_constants(self):
        """Test class constants are properly defined"""
        self.assertEqual(GamepadCalibrator.AXIS_MOVEMENT_THRESHOLD, 0.3)
        self.assertEqual(GamepadCalibrator.FRAME_CONFIRMATION_COUNT, 15)
        self.assertEqual(GamepadCalibrator.STABLE_FRAME_COUNT, 60)
        self.assertEqual(GamepadCalibrator.IDLE_SAMPLE_COUNT, 10)

        # Test step labels
        expected_labels = {
            CalibrationStage.STEERING: "Move the steering axis to its left and right maxima...",
            CalibrationStage.STEERING_CENTER: "Let go of steering to detect center position...",
            CalibrationStage.THROTTLE: "Move the throttle axis to its minimum and maximum positions...",
            CalibrationStage.BRAKE: "Move the brake axis to its minimum and maximum positions..."
        }
        self.assertEqual(GamepadCalibrator.STEP_LABELS, expected_labels)

        # Test step order
        expected_order = [
            CalibrationStage.STEERING,
            CalibrationStage.STEERING_CENTER,
            CalibrationStage.THROTTLE,
            CalibrationStage.BRAKE
        ]
        self.assertEqual(GamepadCalibrator.STEP_ORDER, expected_order)

    def test_start(self):
        """Test calibration start"""
        self.calibrator.start()

        # Check callback was called
        self.mock_on_start.assert_called_once()

        # Check state changes
        self.assertEqual(self.calibrator.state, CalibratorState.ACTIVE)
        self.assertEqual(self.calibrator.stage, CalibrationStage.STEERING)

    def test_start_without_callback(self):
        """Test start without on_start callback"""
        calibrator = GamepadCalibrator()

        # Should not raise exception
        calibrator.start()

        self.assertEqual(calibrator.state, CalibratorState.ACTIVE)
        self.assertEqual(calibrator.stage, CalibrationStage.STEERING)

    def test_get_steps(self):
        """Test get_steps method"""
        # Test when no stage is active
        steps = self.calibrator.get_steps()
        self.assertEqual(len(steps), 4)

        # All steps should be inactive initially
        for label, is_active in steps:
            self.assertFalse(is_active)

        # Test when steering stage is active
        self.calibrator.stage = CalibrationStage.STEERING
        self.calibrator.state = CalibratorState.ACTIVE

        steps = self.calibrator.get_steps()
        self.assertTrue(steps[0][1])  # First step should be active
        for i in range(1, len(steps)):
            self.assertFalse(steps[i][1])

        # Test when paused with pending stage
        self.calibrator.state = CalibratorState.PAUSE
        self.calibrator.pending_stage = CalibrationStage.THROTTLE

        steps = self.calibrator.get_steps()
        self.assertTrue(steps[2][1])  # Throttle step should be active

    def test_queue_next_stage_with_dialog(self):
        """Test _queue_next_stage_with_dialog method"""
        next_stage = CalibrationStage.THROTTLE

        self.calibrator._queue_next_stage_with_dialog(next_stage)

        # Check dialog interactions
        self.mock_dialog.set_text.assert_called_once_with([GamepadCalibrator.STEP_LABELS[next_stage]])
        self.assertEqual(self.mock_dialog.on_confirm, self.calibrator._resume_calibration)
        self.mock_dialog.show.assert_called_once()

        # Check state changes
        self.assertTrue(self.calibrator.waiting_for_user)
        self.assertEqual(self.calibrator.pending_stage, next_stage)
        self.assertEqual(self.calibrator.state, CalibratorState.PAUSE)

    def test_queue_next_stage_without_dialog(self):
        """Test _queue_next_stage_with_dialog without dialog"""
        calibrator = GamepadCalibrator()  # No dialog provided
        next_stage = CalibrationStage.THROTTLE

        # Store initial state
        initial_waiting = calibrator.waiting_for_user
        initial_pending = calibrator.pending_stage
        initial_state = calibrator.state

        # Should not raise exception
        calibrator._queue_next_stage_with_dialog(next_stage)

        # Since there's no dialog, the method should do nothing - all values should remain unchanged
        self.assertEqual(calibrator.waiting_for_user, initial_waiting)
        self.assertEqual(calibrator.pending_stage, initial_pending)
        self.assertEqual(calibrator.state, initial_state)

    def test_resume_calibration(self):
        """Test _resume_calibration method"""
        # Set up paused state
        self.calibrator.pending_stage = CalibrationStage.BRAKE
        self.calibrator.state = CalibratorState.PAUSE
        self.calibrator.waiting_for_user = True

        self.calibrator._resume_calibration()

        # Check state changes
        self.assertEqual(self.calibrator.stage, CalibrationStage.BRAKE)
        self.assertIsNone(self.calibrator.pending_stage)
        self.assertEqual(self.calibrator.state, CalibratorState.ACTIVE)
        self.assertFalse(self.calibrator.waiting_for_user)

        # Check dialog interaction
        self.mock_dialog.hide.assert_called_once()

    def test_update_paused_state(self):
        """Test update method when in paused state"""
        self.calibrator.state = CalibratorState.PAUSE
        axes = [0.0, 0.0, 0.0]

        self.calibrator.update(axes)

        # Should do nothing when paused
        # No way to directly test this, but it shouldn't crash

    def test_update_inactive_state(self):
        """Test update method when not active"""
        self.calibrator.state = CalibratorState.COMPLETE
        axes = [0.0, 0.0, 0.0]

        self.calibrator.update(axes)

        # Should do nothing when not active

    def test_detect_and_record_axis_initial_baseline(self):
        """Test axis detection with initial baseline setup"""
        axes = [0.5, 0.3, 0.1]
        axis_data = self.calibrator.axes["steering"]

        # First call should set baseline
        self.calibrator._detect_and_record_axis("steering", axes)

        self.assertEqual(axis_data.baseline, axes)
        self.assertIsNone(axis_data.axis)

    @patch('builtins.print')
    def test_detect_and_record_axis_detection(self, mock_print):
        """Test axis detection with movement threshold"""
        axis_data = self.calibrator.axes["steering"]
        axis_data.baseline = [0.0, 0.0, 0.0]

        # Simulate movement on axis 0 above threshold
        for _ in range(GamepadCalibrator.FRAME_CONFIRMATION_COUNT):
            axes = [0.5, 0.0, 0.0]  # Movement on axis 0
            self.calibrator._detect_and_record_axis("steering", axes)

        # Should detect axis 0
        self.assertEqual(axis_data.axis, 0)
        mock_print.assert_called_with("Steering axis identified: 0")

    def test_detect_and_record_axis_below_threshold(self):
        """Test axis detection with movement below threshold"""
        axis_data = self.calibrator.axes["steering"]
        axis_data.baseline = [0.0, 0.0, 0.0]

        # Simulate small movement below threshold
        axes = [0.1, 0.0, 0.0]  # Small movement
        self.calibrator._detect_and_record_axis("steering", axes)

        self.assertIsNone(axis_data.axis)
        self.assertEqual(axis_data.detection_frames, 0)

    @patch('builtins.print')
    def test_detect_and_record_axis_recording_values(self, mock_print):
        """Test recording axis values after detection"""
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0  # Axis already detected

        # Mock the next stage callback
        mock_next_stage = MagicMock()

        # Record values for stable frame count
        for i in range(GamepadCalibrator.STABLE_FRAME_COUNT + 1):
            axes = [0.8, 0.0, 0.0]
            self.calibrator._detect_and_record_axis(
                "steering", axes, next_stage=CalibrationStage.STEERING_CENTER
            )

        # Should have recorded values and called next stage
        self.assertGreater(len(axis_data.max_values), 0)
        mock_print.assert_called()

    def test_detect_and_record_axis_with_exclusions(self):
        """Test axis detection with excluded axes"""
        # Set up steering axis as already detected
        self.calibrator.axes["steering"].axis = 0

        throttle_data = self.calibrator.axes["throttle"]
        throttle_data.baseline = [0.0, 0.0, 0.0]

        # Simulate movement on axis 1 (should be detected since axis 0 is excluded)
        for _ in range(GamepadCalibrator.FRAME_CONFIRMATION_COUNT):
            axes = [0.0, 0.5, 0.0]
            self.calibrator._detect_and_record_axis("throttle", axes, exclude=["steering"])

        self.assertEqual(throttle_data.axis, 1)

    def test_record_center_idle_initial_value(self):
        """Test _record_center_idle initial value recording"""
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0

        axes = [0.2, 0.0, 0.0]
        self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        self.assertEqual(axis_data.idle_last, 0.2)

    @patch('builtins.print')
    def test_record_center_idle_stable_detection(self, mock_print):
        """Test center idle detection when stable"""
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.idle_last = 0.2

        # Simulate stable values
        for _ in range(GamepadCalibrator.STABLE_FRAME_COUNT + GamepadCalibrator.IDLE_SAMPLE_COUNT):
            axes = [0.2, 0.0, 0.0]  # Stable value
            self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        # Should have collected idle samples
        self.assertGreaterEqual(len(axis_data.idle_samples), GamepadCalibrator.IDLE_SAMPLE_COUNT)
        mock_print.assert_called()

    def test_record_center_idle_unstable_reset(self):
        """Test center idle detection resets on unstable values"""
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.idle_last = 0.2
        axis_data.idle_stable = 30  # Some progress

        # Simulate unstable value
        axes = [0.4, 0.0, 0.0]  # Changed value
        self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        self.assertEqual(axis_data.idle_stable, 0)
        self.assertEqual(axis_data.idle_last, 0.4)

    def test_complete(self):
        """Test calibration completion"""
        self.calibrator._complete()

        # Check state changes
        self.assertEqual(self.calibrator.state, CalibratorState.COMPLETE)
        self.assertIsNone(self.calibrator.stage)

        # Check callback was called
        self.mock_on_done.assert_called_once()

    def test_complete_without_callback(self):
        """Test completion without on_done callback"""
        calibrator = GamepadCalibrator()

        # Should not raise exception
        calibrator._complete()

        self.assertEqual(calibrator.state, CalibratorState.COMPLETE)
        self.assertIsNone(calibrator.stage)

    def test_update_steering_stage(self):
        """Test update method in steering stage"""
        self.calibrator.start()  # Sets stage to STEERING

        with patch.object(self.calibrator, '_detect_and_record_axis') as mock_detect:
            axes = [0.5, 0.0, 0.0]
            self.calibrator.update(axes)

            mock_detect.assert_called_once_with(
                'steering', axes, next_stage=CalibrationStage.STEERING_CENTER
            )

    def test_update_steering_center_stage(self):
        """Test update method in steering center stage"""
        self.calibrator.stage = CalibrationStage.STEERING_CENTER
        self.calibrator.state = CalibratorState.ACTIVE

        with patch.object(self.calibrator, '_record_center_idle') as mock_record:
            axes = [0.2, 0.0, 0.0]
            self.calibrator.update(axes)

            mock_record.assert_called_once_with(
                'steering', axes, next_stage=CalibrationStage.THROTTLE
            )

    def test_update_throttle_stage(self):
        """Test update method in throttle stage"""
        self.calibrator.stage = CalibrationStage.THROTTLE
        self.calibrator.state = CalibratorState.ACTIVE

        with patch.object(self.calibrator, '_detect_and_record_axis') as mock_detect:
            axes = [0.0, 0.8, 0.0]
            self.calibrator.update(axes)

            mock_detect.assert_called_once_with(
                'throttle', axes, exclude=['steering'], next_stage=CalibrationStage.BRAKE
            )

    def test_update_brake_stage(self):
        """Test update method in brake stage"""
        self.calibrator.stage = CalibrationStage.BRAKE
        self.calibrator.state = CalibratorState.ACTIVE

        with patch.object(self.calibrator, '_detect_and_record_axis') as mock_detect:
            axes = [0.0, 0.0, 0.9]
            self.calibrator.update(axes)

            mock_detect.assert_called_once_with(
                'brake', axes, exclude=['steering'], on_complete=self.calibrator._complete
            )

    def test_get_settings_empty(self):
        """Test get_settings with no calibration data"""
        settings = self.calibrator.get_settings()

        expected = {
            "steering": {"axis": None, "min": 0, "max": 0, "center": None},
            "throttle": {"axis": None, "min": 0, "max": 0, "center": None},
            "brake": {"axis": None, "min": 0, "max": 0, "center": None}
        }

        self.assertEqual(settings, expected)

    def test_get_settings_with_data(self):
        """Test get_settings with calibration data"""
        # Set up some test data
        steering_data = self.calibrator.axes["steering"]
        steering_data.axis = 0
        steering_data.max_values = [0.1, 0.8, 0.2]
        steering_data.idle_samples = [0.45, 0.48, 0.47]

        throttle_data = self.calibrator.axes["throttle"]
        throttle_data.axis = 1
        throttle_data.max_values = [0.0, 1.0, 0.5]

        brake_data = self.calibrator.axes["brake"]
        brake_data.axis = 2
        brake_data.max_values = [0.2, 0.9]

        settings = self.calibrator.get_settings()

        # Check steering settings (has center)
        self.assertEqual(settings["steering"]["axis"], 0)
        self.assertEqual(settings["steering"]["min"], 0.1)
        self.assertEqual(settings["steering"]["max"], 0.8)
        self.assertAlmostEqual(settings["steering"]["center"], 0.466667, places=5)

        # Check throttle settings (no center)
        self.assertEqual(settings["throttle"]["axis"], 1)
        self.assertEqual(settings["throttle"]["min"], 0.0)
        self.assertEqual(settings["throttle"]["max"], 1.0)
        self.assertIsNone(settings["throttle"]["center"])

        # Check brake settings (no center)
        self.assertEqual(settings["brake"]["axis"], 2)
        self.assertEqual(settings["brake"]["min"], 0.2)
        self.assertEqual(settings["brake"]["max"], 0.9)
        self.assertIsNone(settings["brake"]["center"])

    def test_full_calibration_workflow(self):
        """Integration test for full calibration workflow"""
        # Start calibration
        self.calibrator.start()
        self.assertEqual(self.calibrator.stage, CalibrationStage.STEERING)

        # Mock the axis detection and completion process
        with patch.object(self.calibrator, '_detect_and_record_axis') as mock_detect, \
             patch.object(self.calibrator, '_record_center_idle') as mock_record_idle:

            # Simulate steering detection completion
            def steering_complete(*args, **kwargs):
                self.calibrator._queue_next_stage_with_dialog(CalibrationStage.STEERING_CENTER)

            mock_detect.side_effect = steering_complete

            axes = [0.5, 0.0, 0.0]
            self.calibrator.update(axes)

            # Should be paused waiting for user
            self.assertEqual(self.calibrator.state, CalibratorState.PAUSE)
            self.assertEqual(self.calibrator.pending_stage, CalibrationStage.STEERING_CENTER)

            # Resume calibration
            self.calibrator._resume_calibration()
            self.assertEqual(self.calibrator.stage, CalibrationStage.STEERING_CENTER)
            self.assertEqual(self.calibrator.state, CalibratorState.ACTIVE)

    def test_axis_detection_frame_counting(self):
        """Test frame counting for axis detection"""
        axis_data = self.calibrator.axes["steering"]
        axis_data.baseline = [0.0, 0.0, 0.0]

        # Test partial detection (not enough frames)
        for _ in range(GamepadCalibrator.FRAME_CONFIRMATION_COUNT - 1):
            axes = [0.5, 0.0, 0.0]
            self.calibrator._detect_and_record_axis("steering", axes)

        # Should not detect yet
        self.assertIsNone(axis_data.axis)
        self.assertEqual(axis_data.detection_frames, GamepadCalibrator.FRAME_CONFIRMATION_COUNT - 1)

        # One more frame should trigger detection
        self.calibrator._detect_and_record_axis("steering", axes)
        self.assertEqual(axis_data.axis, 0)

    def test_max_value_stability_tracking(self):
        """Test max value stability tracking"""
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0

        # Add initial value - this should initialize max_last and then increment max_stable
        axes = [0.5, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)

        # After first call: max_last=0.5, max_stable=1
        # (because after setting max_last, the condition 0.5 > 0.51 is false, so max_stable increments)
        self.assertEqual(axis_data.max_last, 0.5)
        self.assertEqual(axis_data.max_stable, 1)

        # Add the same value again - this should increment max_stable to 2
        axes = [0.5, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)

        # After second call: max_stable should be 2
        self.assertEqual(axis_data.max_stable, 2)


if __name__ == '__main__':
    unittest.main()