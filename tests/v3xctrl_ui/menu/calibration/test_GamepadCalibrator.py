import unittest
from unittest.mock import MagicMock, patch

from v3xctrl_ui.menu.calibration.defs import AxisCalibrationData, CalibrationStage, CalibratorState
from v3xctrl_ui.menu.calibration.GamepadCalibrator import GamepadCalibrator
from v3xctrl_ui.menu.DialogBox import DialogBox


class MockClock:
    def __init__(self):
        self.time = 0.0

    def __call__(self):
        return self.time

    def advance(self, seconds: float):
        self.time += seconds


class TestGamepadCalibrator(unittest.TestCase):
    def setUp(self):
        self.mock_on_start = MagicMock()
        self.mock_on_done = MagicMock()
        self.mock_dialog = MagicMock(spec=DialogBox)
        self.clock = MockClock()

        self.calibrator = GamepadCalibrator(
            on_start=self.mock_on_start, on_done=self.mock_on_done, dialog=self.mock_dialog, clock=self.clock
        )

    def test_initialization(self):
        self.assertEqual(self.calibrator.on_start, self.mock_on_start)
        self.assertEqual(self.calibrator.on_done, self.mock_on_done)
        self.assertEqual(self.calibrator.dialog, self.mock_dialog)

        self.assertIsNone(self.calibrator.stage)
        self.assertEqual(self.calibrator.state, CalibratorState.PAUSE)
        self.assertIsNone(self.calibrator.pending_stage)
        self.assertFalse(self.calibrator.waiting_for_user)

        self.assertIn("steering", self.calibrator.axes)
        self.assertIn("throttle", self.calibrator.axes)
        self.assertIn("brake", self.calibrator.axes)

        for axis_name in ["steering", "throttle", "brake"]:
            axis_data = self.calibrator.axes[axis_name]
            self.assertIsInstance(axis_data, AxisCalibrationData)

    def test_initialization_without_callbacks(self):
        calibrator = GamepadCalibrator()

        self.assertIsNone(calibrator.on_start)
        self.assertIsNone(calibrator.on_done)
        self.assertIsNone(calibrator.dialog)

    def test_start(self):
        self.calibrator.start()

        self.mock_on_start.assert_called_once()

        self.assertEqual(self.calibrator.state, CalibratorState.ACTIVE)
        self.assertEqual(self.calibrator.stage, CalibrationStage.STEERING)

    def test_start_without_callback(self):
        calibrator = GamepadCalibrator(clock=self.clock)

        calibrator.start()

        self.assertEqual(calibrator.state, CalibratorState.ACTIVE)
        self.assertEqual(calibrator.stage, CalibrationStage.STEERING)

    def test_get_steps(self):
        steps = self.calibrator.get_steps()
        self.assertEqual(len(steps), 4)

        for _label, is_active in steps:
            self.assertFalse(is_active)

        self.calibrator.stage = CalibrationStage.STEERING
        self.calibrator.state = CalibratorState.ACTIVE

        steps = self.calibrator.get_steps()
        self.assertTrue(steps[0][1])
        for i in range(1, len(steps)):
            self.assertFalse(steps[i][1])

        self.calibrator.state = CalibratorState.PAUSE
        self.calibrator.pending_stage = CalibrationStage.THROTTLE

        steps = self.calibrator.get_steps()
        self.assertTrue(steps[2][1])

    def test_queue_next_stage_with_dialog(self):
        next_stage = CalibrationStage.THROTTLE

        self.calibrator._queue_next_stage_with_dialog(next_stage)

        self.mock_dialog.set_text.assert_called_once_with([GamepadCalibrator.STEP_LABELS[next_stage]])
        self.assertEqual(self.mock_dialog.on_confirm, self.calibrator._resume_calibration)
        self.mock_dialog.show.assert_called_once()

        self.assertTrue(self.calibrator.waiting_for_user)
        self.assertEqual(self.calibrator.pending_stage, next_stage)
        self.assertEqual(self.calibrator.state, CalibratorState.PAUSE)

    def test_queue_next_stage_without_dialog(self):
        calibrator = GamepadCalibrator(clock=self.clock)
        next_stage = CalibrationStage.THROTTLE

        initial_waiting = calibrator.waiting_for_user
        initial_pending = calibrator.pending_stage
        initial_state = calibrator.state

        calibrator._queue_next_stage_with_dialog(next_stage)

        self.assertEqual(calibrator.waiting_for_user, initial_waiting)
        self.assertEqual(calibrator.pending_stage, initial_pending)
        self.assertEqual(calibrator.state, initial_state)

    def test_resume_calibration(self):
        self.calibrator.pending_stage = CalibrationStage.BRAKE
        self.calibrator.state = CalibratorState.PAUSE
        self.calibrator.waiting_for_user = True

        self.calibrator._resume_calibration()

        self.assertEqual(self.calibrator.stage, CalibrationStage.BRAKE)
        self.assertIsNone(self.calibrator.pending_stage)
        self.assertEqual(self.calibrator.state, CalibratorState.ACTIVE)
        self.assertFalse(self.calibrator.waiting_for_user)

        self.mock_dialog.hide.assert_called_once()

    def test_update_paused_state(self):
        self.calibrator.state = CalibratorState.PAUSE
        axes = [0.0, 0.0, 0.0]

        self.calibrator.update(axes)

    def test_update_inactive_state(self):
        self.calibrator.state = CalibratorState.COMPLETE
        axes = [0.0, 0.0, 0.0]

        self.calibrator.update(axes)

    def test_detect_and_record_axis_initial_baseline(self):
        axes = [0.5, 0.3, 0.1]
        axis_data = self.calibrator.axes["steering"]

        self.calibrator._detect_and_record_axis("steering", axes)

        self.assertEqual(axis_data.baseline, axes)
        self.assertIsNone(axis_data.axis)

    @patch("logging.info")
    def test_detect_and_record_axis_detection(self, mock_logging):
        axis_data = self.calibrator.axes["steering"]
        axis_data.baseline = [0.0, 0.0, 0.0]

        axes = [0.5, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)
        self.assertIsNone(axis_data.axis)

        self.clock.advance(GamepadCalibrator.DETECTION_TIME)
        self.calibrator._detect_and_record_axis("steering", axes)

        self.assertEqual(axis_data.axis, 0)
        mock_logging.assert_called_with("Steering axis identified: 0")

    def test_detect_and_record_axis_below_threshold(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.baseline = [0.0, 0.0, 0.0]

        axes = [0.1, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)

        self.assertIsNone(axis_data.axis)
        self.assertIsNone(axis_data.detection_start)

    @patch("logging.info")
    def test_detect_and_record_axis_recording_values(self, mock_logging):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.max_last = 0.8
        axis_data.max_stable_since = 0.0
        axis_data.min_last = -0.8
        axis_data.min_stable_since = 0.0
        axis_data.max_values = [-0.8, 0.5]

        self.clock.advance(GamepadCalibrator.STABLE_TIME)

        axes = [0.8, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes, next_stage=CalibrationStage.STEERING_CENTER)

        mock_logging.assert_called_with("Steering axis min/max: -0.80/0.80")

    def test_detect_and_record_axis_with_exclusions(self):
        self.calibrator.axes["steering"].axis = 0

        throttle_data = self.calibrator.axes["throttle"]
        throttle_data.baseline = [0.0, 0.0, 0.0]

        axes = [0.0, 0.5, 0.0]
        self.calibrator._detect_and_record_axis("throttle", axes, exclude=["steering"])

        self.clock.advance(GamepadCalibrator.DETECTION_TIME)
        self.calibrator._detect_and_record_axis("throttle", axes, exclude=["steering"])

        self.assertEqual(throttle_data.axis, 1)

    def test_record_center_idle_initial_value(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0

        axes = [0.2, 0.0, 0.0]
        self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        self.assertEqual(axis_data.idle_last, 0.2)

    @patch("logging.info")
    def test_record_center_idle_stable_detection(self, mock_logging):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.idle_last = 0.2
        axis_data.idle_stable_since = 0.0
        axis_data.idle_samples = [0.2] * (GamepadCalibrator.IDLE_SAMPLE_COUNT - 1)

        self.clock.advance(GamepadCalibrator.STABLE_TIME)

        axes = [0.2, 0.0, 0.0]
        self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        self.assertGreaterEqual(len(axis_data.idle_samples), GamepadCalibrator.IDLE_SAMPLE_COUNT)
        mock_logging.assert_called_with("Steering axis idle: 0.20")

    def test_record_center_idle_unstable_reset(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.idle_last = 0.2
        axis_data.idle_stable_since = 0.0

        axes = [0.4, 0.0, 0.0]
        self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        self.assertIsNone(axis_data.idle_stable_since)
        self.assertEqual(axis_data.idle_last, 0.4)

    def test_complete(self):
        self.calibrator._complete()

        self.assertEqual(self.calibrator.state, CalibratorState.COMPLETE)
        self.assertIsNone(self.calibrator.stage)

        self.mock_on_done.assert_called_once()

    def test_complete_without_callback(self):
        calibrator = GamepadCalibrator(clock=self.clock)

        calibrator._complete()

        self.assertEqual(calibrator.state, CalibratorState.COMPLETE)
        self.assertIsNone(calibrator.stage)

    def test_update_steering_stage(self):
        self.calibrator.start()

        with patch.object(self.calibrator, "_detect_and_record_axis") as mock_detect:
            axes = [0.5, 0.0, 0.0]
            self.calibrator.update(axes)

            mock_detect.assert_called_once_with("steering", axes, next_stage=CalibrationStage.STEERING_CENTER)

    def test_update_steering_center_stage(self):
        self.calibrator.stage = CalibrationStage.STEERING_CENTER
        self.calibrator.state = CalibratorState.ACTIVE

        with patch.object(self.calibrator, "_record_center_idle") as mock_record:
            axes = [0.2, 0.0, 0.0]
            self.calibrator.update(axes)

            mock_record.assert_called_once_with("steering", axes, next_stage=CalibrationStage.THROTTLE)

    def test_update_throttle_stage(self):
        self.calibrator.stage = CalibrationStage.THROTTLE
        self.calibrator.state = CalibratorState.ACTIVE

        with patch.object(self.calibrator, "_detect_and_record_axis") as mock_detect:
            axes = [0.0, 0.8, 0.0]
            self.calibrator.update(axes)

            mock_detect.assert_called_once_with(
                "throttle", axes, exclude=["steering"], next_stage=CalibrationStage.BRAKE
            )

    def test_update_brake_stage(self):
        self.calibrator.stage = CalibrationStage.BRAKE
        self.calibrator.state = CalibratorState.ACTIVE

        with patch.object(self.calibrator, "_detect_and_record_axis") as mock_detect:
            axes = [0.0, 0.0, 0.9]
            self.calibrator.update(axes)

            mock_detect.assert_called_once_with(
                "brake", axes, exclude=["steering"], on_complete=self.calibrator._complete
            )

    def test_get_settings_empty(self):
        expected = {
            "steering": {"axis": None, "min": 0, "max": 0, "center": None},
            "throttle": {"axis": None, "min": 0, "max": 0, "center": None},
            "brake": {"axis": None, "min": 0, "max": 0, "center": None},
        }

        self.assertEqual(self.calibrator.get_settings(), expected)

    def test_get_settings_with_data(self):
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

        self.assertEqual(settings["steering"]["axis"], 0)
        self.assertEqual(settings["steering"]["min"], 0.1)
        self.assertEqual(settings["steering"]["max"], 0.8)
        self.assertAlmostEqual(settings["steering"]["center"], 0.466667, places=5)

        self.assertEqual(settings["throttle"]["axis"], 1)
        self.assertEqual(settings["throttle"]["min"], 0.0)
        self.assertEqual(settings["throttle"]["max"], 1.0)
        self.assertIsNone(settings["throttle"]["center"])

        self.assertEqual(settings["brake"]["axis"], 2)
        self.assertEqual(settings["brake"]["min"], 0.2)
        self.assertEqual(settings["brake"]["max"], 0.9)
        self.assertIsNone(settings["brake"]["center"])

    def test_full_calibration_workflow(self):
        self.calibrator.start()
        self.assertEqual(self.calibrator.stage, CalibrationStage.STEERING)

        with (
            patch.object(self.calibrator, "_detect_and_record_axis") as mock_detect,
            patch.object(self.calibrator, "_record_center_idle"),
        ):

            def steering_complete(*args, **kwargs):
                self.calibrator._queue_next_stage_with_dialog(CalibrationStage.STEERING_CENTER)

            mock_detect.side_effect = steering_complete

            axes = [0.5, 0.0, 0.0]
            self.calibrator.update(axes)

            self.assertEqual(self.calibrator.state, CalibratorState.PAUSE)
            self.assertEqual(self.calibrator.pending_stage, CalibrationStage.STEERING_CENTER)

            self.calibrator._resume_calibration()
            self.assertEqual(self.calibrator.stage, CalibrationStage.STEERING_CENTER)
            self.assertEqual(self.calibrator.state, CalibratorState.ACTIVE)

    def test_axis_detection_requires_sustained_movement(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.baseline = [0.0, 0.0, 0.0]

        # Movement detected but not long enough
        axes = [0.5, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)
        self.assertIsNone(axis_data.axis)
        self.assertIsNotNone(axis_data.detection_start)

        # Advance time but not enough
        self.clock.advance(GamepadCalibrator.DETECTION_TIME - 0.1)
        self.calibrator._detect_and_record_axis("steering", axes)
        self.assertIsNone(axis_data.axis)

        # Advance past threshold
        self.clock.advance(0.1)
        self.calibrator._detect_and_record_axis("steering", axes)
        self.assertEqual(axis_data.axis, 0)

    def test_axis_detection_resets_on_no_movement(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.baseline = [0.0, 0.0, 0.0]

        # Start detection
        axes = [0.5, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)
        self.assertIsNotNone(axis_data.detection_start)

        # Movement stops - resets detection
        axes = [0.0, 0.0, 0.0]
        self.clock.advance(0.1)
        self.calibrator._detect_and_record_axis("steering", axes)
        self.assertIsNone(axis_data.detection_start)

    def test_max_value_stability_tracking(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0

        axes = [0.5, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)

        self.assertEqual(axis_data.max_last, 0.5)
        self.assertIsNotNone(axis_data.max_stable_since)

        # Same value - still stable
        self.clock.advance(0.1)
        self.calibrator._detect_and_record_axis("steering", axes)
        self.assertEqual(axis_data.max_last, 0.5)

    def test_get_steps_with_no_active_stage(self):
        self.calibrator.stage = None
        self.calibrator.state = CalibratorState.ACTIVE

        steps = self.calibrator.get_steps()

        for _label, is_active in steps:
            self.assertFalse(is_active)

    def test_get_settings_empty_max_values(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.max_values = []

        settings = self.calibrator.get_settings()

        self.assertEqual(settings["steering"]["min"], 0)
        self.assertEqual(settings["steering"]["max"], 0)

    def test_detect_and_record_axis_max_last_none_branch(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.max_last = None
        axis_data.max_values = []

        axes = [0.5, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)

        self.assertEqual(axis_data.max_last, 0.5)
        self.assertIsNotNone(axis_data.max_stable_since)

    def test_detect_and_record_axis_significant_increase(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.max_last = 0.3
        axis_data.max_stable_since = 0.0
        axis_data.max_values = [0.1, 0.2, 0.3]

        self.clock.advance(1.0)
        axes = [0.8, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)

        self.assertEqual(axis_data.max_last, 0.8)
        self.assertEqual(axis_data.max_stable_since, self.clock.time)

    def test_record_center_idle_none_initial(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.idle_last = None

        axes = [0.2, 0.0, 0.0]
        self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        self.assertEqual(axis_data.idle_last, 0.2)
        self.assertIsNone(axis_data.idle_stable_since)

    def test_update_with_none_stage(self):
        self.calibrator.state = CalibratorState.ACTIVE
        self.calibrator.stage = None

        axes = [0.5, 0.0, 0.0]
        self.calibrator.update(axes)

    def test_detect_and_record_axis_on_complete_callback(self):
        axis_data = self.calibrator.axes["brake"]
        axis_data.axis = 2
        axis_data.max_stable_since = 0.0
        axis_data.min_stable_since = 0.0
        axis_data.max_last = 0.9
        axis_data.min_last = 0.0
        axis_data.max_values = [0.0, 0.9]

        self.clock.advance(GamepadCalibrator.STABLE_TIME)

        mock_complete = MagicMock()

        axes = [0.0, 0.0, 0.5]
        self.calibrator._detect_and_record_axis("brake", axes, on_complete=mock_complete)

        mock_complete.assert_called_once()

    def test_detect_and_record_axis_next_stage_callback(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.max_stable_since = 0.0
        axis_data.min_stable_since = 0.0
        axis_data.max_last = 0.8
        axis_data.min_last = -0.8
        axis_data.max_values = [-0.8, 0.8]

        self.clock.advance(GamepadCalibrator.STABLE_TIME)

        with patch.object(self.calibrator, "_queue_next_stage_with_dialog") as mock_queue:
            axes = [0.5, 0.0, 0.0]
            self.calibrator._detect_and_record_axis("steering", axes, next_stage=CalibrationStage.STEERING_CENTER)

            mock_queue.assert_called_once_with(CalibrationStage.STEERING_CENTER)

    def test_detect_and_record_axis_no_callback_or_next_stage(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.max_stable_since = 0.0
        axis_data.max_values = [0.1, 0.9]

        axes = [0.5, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)

    def test_record_center_idle_insufficient_samples(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.idle_last = 0.2
        axis_data.idle_stable_since = 0.0
        axis_data.idle_samples = [0.21, 0.22]

        self.clock.advance(GamepadCalibrator.STABLE_TIME)

        axes = [0.2, 0.0, 0.0]
        self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        self.assertEqual(len(axis_data.idle_samples), 3)

    def test_update_invalid_state(self):
        self.calibrator.state = CalibratorState.COMPLETE
        self.calibrator.stage = CalibrationStage.STEERING

        axes = [0.5, 0.0, 0.0]
        self.calibrator.update(axes)

    def test_stable_time_not_reached_does_not_complete(self):
        """Min/max stability must persist for STABLE_TIME before completing."""
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.max_stable_since = 0.0
        axis_data.min_stable_since = 0.0
        axis_data.max_last = 0.8
        axis_data.min_last = -0.8
        axis_data.max_values = [-0.8, 0.8]

        self.clock.advance(GamepadCalibrator.STABLE_TIME - 0.1)

        with patch.object(self.calibrator, "_queue_next_stage_with_dialog") as mock_queue:
            axes = [0.5, 0.0, 0.0]
            self.calibrator._detect_and_record_axis("steering", axes, next_stage=CalibrationStage.STEERING_CENTER)
            mock_queue.assert_not_called()

    def test_idle_stable_time_not_reached_does_not_sample(self):
        """Idle stability must persist for STABLE_TIME before collecting samples."""
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.idle_last = 0.2
        axis_data.idle_stable_since = 0.0

        self.clock.advance(GamepadCalibrator.STABLE_TIME - 0.1)

        axes = [0.2, 0.0, 0.0]
        self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        self.assertEqual(len(axis_data.idle_samples), 0)

    def test_does_not_complete_when_range_too_small(self):
        """Stage must not complete when the range is below AXIS_MOVEMENT_THRESHOLD."""
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.max_stable_since = 0.0
        axis_data.min_stable_since = 0.0
        axis_data.max_last = 0.81
        axis_data.min_last = 0.79
        axis_data.max_values = [0.79, 0.81]

        self.clock.advance(GamepadCalibrator.STABLE_TIME)

        with patch.object(self.calibrator, "_queue_next_stage_with_dialog") as mock_queue:
            axes = [0.8, 0.0, 0.0]
            self.calibrator._detect_and_record_axis("steering", axes, next_stage=CalibrationStage.STEERING_CENTER)

            mock_queue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
