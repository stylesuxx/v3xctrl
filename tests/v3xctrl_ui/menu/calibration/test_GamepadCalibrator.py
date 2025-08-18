import unittest
from unittest.mock import MagicMock, patch

from v3xctrl_ui.menu.calibration.GamepadCalibrator import GamepadCalibrator
from v3xctrl_ui.menu.calibration.defs import CalibrationStage, CalibratorState, AxisCalibrationData
from v3xctrl_ui.menu.DialogBox import DialogBox


class TestGamepadCalibrator(unittest.TestCase):
    def setUp(self):
        self.mock_on_start = MagicMock()
        self.mock_on_done = MagicMock()
        self.mock_dialog = MagicMock(spec=DialogBox)

        self.calibrator = GamepadCalibrator(
            on_start=self.mock_on_start,
            on_done=self.mock_on_done,
            dialog=self.mock_dialog
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

    def test_constants(self):
        self.assertEqual(GamepadCalibrator.AXIS_MOVEMENT_THRESHOLD, 0.3)
        self.assertEqual(GamepadCalibrator.FRAME_CONFIRMATION_COUNT, 15)
        self.assertEqual(GamepadCalibrator.STABLE_FRAME_COUNT, 60)
        self.assertEqual(GamepadCalibrator.IDLE_SAMPLE_COUNT, 10)

        expected_labels = {
            CalibrationStage.STEERING: "Move the steering axis to its left and right maxima...",
            CalibrationStage.STEERING_CENTER: "Let go of steering to detect center position...",
            CalibrationStage.THROTTLE: "Move the throttle axis to its minimum and maximum positions...",
            CalibrationStage.BRAKE: "Move the brake axis to its minimum and maximum positions..."
        }
        self.assertEqual(GamepadCalibrator.STEP_LABELS, expected_labels)

        expected_order = [
            CalibrationStage.STEERING,
            CalibrationStage.STEERING_CENTER,
            CalibrationStage.THROTTLE,
            CalibrationStage.BRAKE
        ]
        self.assertEqual(GamepadCalibrator.STEP_ORDER, expected_order)

    def test_start(self):
        self.calibrator.start()

        self.mock_on_start.assert_called_once()

        self.assertEqual(self.calibrator.state, CalibratorState.ACTIVE)
        self.assertEqual(self.calibrator.stage, CalibrationStage.STEERING)

    def test_start_without_callback(self):
        calibrator = GamepadCalibrator()

        calibrator.start()

        self.assertEqual(calibrator.state, CalibratorState.ACTIVE)
        self.assertEqual(calibrator.stage, CalibrationStage.STEERING)

    def test_get_steps(self):
        steps = self.calibrator.get_steps()
        self.assertEqual(len(steps), 4)

        for label, is_active in steps:
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
        calibrator = GamepadCalibrator()
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

    @patch('builtins.print')
    def test_detect_and_record_axis_detection(self, mock_print):
        axis_data = self.calibrator.axes["steering"]
        axis_data.baseline = [0.0, 0.0, 0.0]

        for _ in range(GamepadCalibrator.FRAME_CONFIRMATION_COUNT):
            axes = [0.5, 0.0, 0.0]
            self.calibrator._detect_and_record_axis("steering", axes)

        self.assertEqual(axis_data.axis, 0)
        mock_print.assert_called_with("Steering axis identified: 0")

    def test_detect_and_record_axis_below_threshold(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.baseline = [0.0, 0.0, 0.0]

        axes = [0.1, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)

        self.assertIsNone(axis_data.axis)
        self.assertEqual(axis_data.detection_frames, 0)

    @patch('builtins.print')
    def test_detect_and_record_axis_recording_values(self, mock_print):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0

        mock_next_stage = MagicMock()

        for i in range(GamepadCalibrator.STABLE_FRAME_COUNT + 1):
            axes = [0.8, 0.0, 0.0]
            self.calibrator._detect_and_record_axis(
                "steering", axes, next_stage=CalibrationStage.STEERING_CENTER
            )

        self.assertGreater(len(axis_data.max_values), 0)
        mock_print.assert_called()

    def test_detect_and_record_axis_with_exclusions(self):
        self.calibrator.axes["steering"].axis = 0

        throttle_data = self.calibrator.axes["throttle"]
        throttle_data.baseline = [0.0, 0.0, 0.0]

        for _ in range(GamepadCalibrator.FRAME_CONFIRMATION_COUNT):
            axes = [0.0, 0.5, 0.0]
            self.calibrator._detect_and_record_axis("throttle", axes, exclude=["steering"])

        self.assertEqual(throttle_data.axis, 1)

    def test_record_center_idle_initial_value(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0

        axes = [0.2, 0.0, 0.0]
        self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        self.assertEqual(axis_data.idle_last, 0.2)

    @patch('builtins.print')
    def test_record_center_idle_stable_detection(self, mock_print):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.idle_last = 0.2

        for _ in range(GamepadCalibrator.STABLE_FRAME_COUNT + GamepadCalibrator.IDLE_SAMPLE_COUNT):
            axes = [0.2, 0.0, 0.0]
            self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        self.assertGreaterEqual(len(axis_data.idle_samples), GamepadCalibrator.IDLE_SAMPLE_COUNT)
        mock_print.assert_called()

    def test_record_center_idle_unstable_reset(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.idle_last = 0.2
        axis_data.idle_stable = 30

        axes = [0.4, 0.0, 0.0]
        self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        self.assertEqual(axis_data.idle_stable, 0)
        self.assertEqual(axis_data.idle_last, 0.4)

    def test_complete(self):
        self.calibrator._complete()

        self.assertEqual(self.calibrator.state, CalibratorState.COMPLETE)
        self.assertIsNone(self.calibrator.stage)

        self.mock_on_done.assert_called_once()

    def test_complete_without_callback(self):
        calibrator = GamepadCalibrator()

        calibrator._complete()

        self.assertEqual(calibrator.state, CalibratorState.COMPLETE)
        self.assertIsNone(calibrator.stage)

    def test_update_steering_stage(self):
        self.calibrator.start()

        with patch.object(self.calibrator, '_detect_and_record_axis') as mock_detect:
            axes = [0.5, 0.0, 0.0]
            self.calibrator.update(axes)

            mock_detect.assert_called_once_with(
                'steering', axes, next_stage=CalibrationStage.STEERING_CENTER
            )

    def test_update_steering_center_stage(self):
        self.calibrator.stage = CalibrationStage.STEERING_CENTER
        self.calibrator.state = CalibratorState.ACTIVE

        with patch.object(self.calibrator, '_record_center_idle') as mock_record:
            axes = [0.2, 0.0, 0.0]
            self.calibrator.update(axes)

            mock_record.assert_called_once_with(
                'steering', axes, next_stage=CalibrationStage.THROTTLE
            )

    def test_update_throttle_stage(self):
        self.calibrator.stage = CalibrationStage.THROTTLE
        self.calibrator.state = CalibratorState.ACTIVE

        with patch.object(self.calibrator, '_detect_and_record_axis') as mock_detect:
            axes = [0.0, 0.8, 0.0]
            self.calibrator.update(axes)

            mock_detect.assert_called_once_with(
                'throttle', axes, exclude=['steering'], next_stage=CalibrationStage.BRAKE
            )

    def test_update_brake_stage(self):
        self.calibrator.stage = CalibrationStage.BRAKE
        self.calibrator.state = CalibratorState.ACTIVE

        with patch.object(self.calibrator, '_detect_and_record_axis') as mock_detect:
            axes = [0.0, 0.0, 0.9]
            self.calibrator.update(axes)

            mock_detect.assert_called_once_with(
                'brake', axes, exclude=['steering'], on_complete=self.calibrator._complete
            )

    def test_get_settings_empty(self):
        expected = {
            "steering": {"axis": None, "min": 0, "max": 0, "center": None},
            "throttle": {"axis": None, "min": 0, "max": 0, "center": None},
            "brake": {"axis": None, "min": 0, "max": 0, "center": None}
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

        with patch.object(self.calibrator, '_detect_and_record_axis') as mock_detect, \
             patch.object(self.calibrator, '_record_center_idle') as mock_record_idle:

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

    def test_axis_detection_frame_counting(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.baseline = [0.0, 0.0, 0.0]

        for _ in range(GamepadCalibrator.FRAME_CONFIRMATION_COUNT - 1):
            axes = [0.5, 0.0, 0.0]
            self.calibrator._detect_and_record_axis("steering", axes)

        self.assertIsNone(axis_data.axis)
        self.assertEqual(axis_data.detection_frames, GamepadCalibrator.FRAME_CONFIRMATION_COUNT - 1)

        self.calibrator._detect_and_record_axis("steering", axes)
        self.assertEqual(axis_data.axis, 0)

    def test_max_value_stability_tracking(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0

        axes = [0.5, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)

        self.assertEqual(axis_data.max_last, 0.5)
        self.assertEqual(axis_data.max_stable, 1)

        axes = [0.5, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)

        self.assertEqual(axis_data.max_stable, 2)

    def test_get_steps_with_no_active_stage(self):
        self.calibrator.stage = None
        self.calibrator.state = CalibratorState.ACTIVE

        steps = self.calibrator.get_steps()

        for label, is_active in steps:
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
        self.assertEqual(axis_data.max_stable, 1)

    def test_detect_and_record_axis_significant_increase(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.max_last = 0.3
        axis_data.max_stable = 5
        axis_data.max_values = [0.1, 0.2, 0.3]

        axes = [0.8, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)

        self.assertEqual(axis_data.max_last, 0.8)
        self.assertEqual(axis_data.max_stable, 0)

    def test_record_center_idle_none_initial(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.idle_last = None

        axes = [0.2, 0.0, 0.0]
        self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        self.assertEqual(axis_data.idle_last, 0.2)
        self.assertEqual(axis_data.idle_stable, 0)

    def test_update_with_none_stage(self):
        self.calibrator.state = CalibratorState.ACTIVE
        self.calibrator.stage = None

        axes = [0.5, 0.0, 0.0]
        self.calibrator.update(axes)

    def test_detect_and_record_axis_on_complete_callback(self):
        axis_data = self.calibrator.axes["brake"]
        axis_data.axis = 2
        axis_data.max_stable = GamepadCalibrator.STABLE_FRAME_COUNT - 1
        axis_data.max_values = [0.1, 0.9]
        axis_data.max_last = 0.9

        mock_complete = MagicMock()

        axes = [0.0, 0.0, 0.5]
        self.calibrator._detect_and_record_axis("brake", axes, on_complete=mock_complete)

        mock_complete.assert_called_once()

    def test_detect_and_record_axis_next_stage_callback(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.max_stable = GamepadCalibrator.STABLE_FRAME_COUNT - 1
        axis_data.max_values = [0.1, 0.9]
        axis_data.max_last = 0.9

        with patch.object(self.calibrator, '_queue_next_stage_with_dialog') as mock_queue:
            axes = [0.5, 0.0, 0.0]
            self.calibrator._detect_and_record_axis("steering", axes, next_stage=CalibrationStage.STEERING_CENTER)

            mock_queue.assert_called_once_with(CalibrationStage.STEERING_CENTER)

    def test_detect_and_record_axis_no_callback_or_next_stage(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.max_stable = GamepadCalibrator.STABLE_FRAME_COUNT
        axis_data.max_values = [0.1, 0.9]

        axes = [0.5, 0.0, 0.0]
        self.calibrator._detect_and_record_axis("steering", axes)

    def test_record_center_idle_insufficient_samples(self):
        axis_data = self.calibrator.axes["steering"]
        axis_data.axis = 0
        axis_data.idle_last = 0.2
        axis_data.idle_stable = GamepadCalibrator.STABLE_FRAME_COUNT
        axis_data.idle_samples = [0.21, 0.22]

        axes = [0.2, 0.0, 0.0]
        self.calibrator._record_center_idle("steering", axes, CalibrationStage.THROTTLE)

        self.assertEqual(len(axis_data.idle_samples), 3)

    def test_update_invalid_state(self):
        self.calibrator.state = CalibratorState.COMPLETE
        self.calibrator.stage = CalibrationStage.STEERING

        axes = [0.5, 0.0, 0.0]
        self.calibrator.update(axes)


if __name__ == '__main__':
    unittest.main()
