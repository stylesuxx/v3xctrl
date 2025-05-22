import pygame
from typing import Optional, Callable, List, Dict, Tuple

from v3xctrl_ui.menu.calibration.defs import CalibrationStage, CalibratorState, AxisCalibrationData


class GamepadCalibrator:
    AXIS_MOVEMENT_THRESHOLD = 0.3
    FRAME_CONFIRMATION_COUNT = 15
    STABLE_FRAME_COUNT = 60
    IDLE_SAMPLE_COUNT = 10
    PAUSE_DURATION_MS = 3000

    STEP_LABELS: Dict[CalibrationStage, str] = {
        CalibrationStage.STEERING: "Move the steering axis to its left and right maxima...",
        CalibrationStage.STEERING_CENTER: "Let go of steering to detect center position...",
        CalibrationStage.THROTTLE: "Move the throttle axis to its minimum and maximum positions...",
        CalibrationStage.BRAKE: "Move the brake axis to its minimum and maximum positions..."
    }

    STEP_ORDER: List[CalibrationStage] = list(STEP_LABELS.keys())

    def __init__(self,
                 on_start: Optional[Callable[[], None]] = None,
                 on_done: Optional[Callable[[], None]] = None):
        self.on_start = on_start
        self.on_done = on_done

        self.stage: Optional[CalibrationStage] = None
        self.state: CalibratorState = CalibratorState.PAUSE
        self.pause_start_time: int = 0
        self.pending_stage: Optional[CalibrationStage] = None
        self.axes: Dict[str, AxisCalibrationData] = {
            "steering": AxisCalibrationData(),
            "throttle": AxisCalibrationData(),
            "brake": AxisCalibrationData()
        }

    def start(self) -> None:
        if self.on_start:
            self.on_start()

        self.state = CalibratorState.ACTIVE
        self.stage = CalibrationStage.STEERING

    def _pause_and_queue(self, next_stage: CalibrationStage) -> None:
        self.state = CalibratorState.PAUSE
        self.pause_start_time = pygame.time.get_ticks()
        self.pending_stage = next_stage

    def get_steps(self) -> List[Tuple[str, bool]]:
        steps: List[Tuple[str, bool]] = []
        active_stage = self.pending_stage if self.state == CalibratorState.PAUSE else self.stage
        for key in self.STEP_ORDER:
            label = self.STEP_LABELS.get(key)
            if label:
                steps.append((label, key == active_stage))

        return steps

    def update(self, axes: List[float]) -> None:
        if self.state == CalibratorState.PAUSE:
            if pygame.time.get_ticks() - self.pause_start_time > self.PAUSE_DURATION_MS:
                self.stage = self.pending_stage
                self.pending_stage = None
                self.state = CalibratorState.ACTIVE

            return

        if self.state != CalibratorState.ACTIVE or self.stage is None:
            return

        if self.stage == CalibrationStage.STEERING:
            self._detect_and_record_axis('steering', axes, next_stage=CalibrationStage.STEERING_CENTER)
        elif self.stage == CalibrationStage.STEERING_CENTER:
            self._record_center_idle('steering', axes, next_stage=CalibrationStage.THROTTLE)
        elif self.stage == CalibrationStage.THROTTLE:
            self._detect_and_record_axis('throttle', axes, exclude=['steering'], next_stage=CalibrationStage.BRAKE)
        elif self.stage == CalibrationStage.BRAKE:
            self._detect_and_record_axis('brake', axes, exclude=['steering'], on_complete=self._complete)

    def _detect_and_record_axis(self,
                                name: str,
                                axes: List[float],
                                exclude: List[str] = [],
                                next_stage: Optional[CalibrationStage] = None,
                                on_complete: Optional[Callable[[], None]] = None) -> None:
        axis_data = self.axes[name]
        excluded_indices = [self.axes[e].axis for e in exclude if self.axes[e].axis is not None]

        if axis_data.axis is None:
            if axis_data.baseline is None:
                axis_data.baseline = axes.copy()
            else:
                diffs = [
                    abs(a - b) if i not in excluded_indices else 0
                    for i, (a, b) in enumerate(zip(axes, axis_data.baseline))
                ]
                axis = max(range(len(diffs)), key=lambda i: diffs[i])
                if diffs[axis] > self.AXIS_MOVEMENT_THRESHOLD:
                    axis_data.detection_frames += 1
                    if axis_data.detection_frames >= self.FRAME_CONFIRMATION_COUNT:
                        axis_data.axis = axis
                        print(f"{name.capitalize()} axis identified: {axis}")
                else:
                    axis_data.detection_frames = 0
        else:
            i = axis_data.axis
            axis_data.max_values.append(axes[i])
            current_max = max(axis_data.max_values)
            if axis_data.max_last is None:
                axis_data.max_last = current_max
                axis_data.max_stable = 0
            if current_max > axis_data.max_last + 0.01:
                axis_data.max_last = current_max
                axis_data.max_stable = 0
            else:
                axis_data.max_stable += 1

            if axis_data.max_stable >= self.STABLE_FRAME_COUNT:
                min_val = min(axis_data.max_values)
                max_val = max(axis_data.max_values)
                print(f"{name.capitalize()} axis min/max: {min_val:.2f}/{max_val:.2f}")
                if on_complete:
                    on_complete()
                elif next_stage:
                    self._pause_and_queue(next_stage)

    def _record_center_idle(self, name: str, axes: List[float], next_stage: CalibrationStage) -> None:
        axis_data = self.axes[name]
        i = axis_data.axis
        value = axes[i]
        if axis_data.idle_last is None:
            axis_data.idle_last = value
        else:
            if abs(value - axis_data.idle_last) < 0.05:
                axis_data.idle_stable += 1
                if axis_data.idle_stable >= self.STABLE_FRAME_COUNT:
                    axis_data.idle_samples.append(value)
                    if len(axis_data.idle_samples) >= self.IDLE_SAMPLE_COUNT:
                        avg = sum(axis_data.idle_samples) / len(axis_data.idle_samples)
                        print(f"{name.capitalize()} axis idle: {avg:.2f}")
                        self._pause_and_queue(next_stage)
            else:
                axis_data.idle_stable = 0

            axis_data.idle_last = value

    def _complete(self) -> None:
        self.state = CalibratorState.COMPLETE
        self.stage = None

        if self.on_done:
            self.on_done()

    def get_settings(self) -> Dict[str, Dict[str, Optional[float | int]]]:
        return {
            name: {
                "axis": axis.axis,
                "min": min(axis.max_values) if axis.max_values else 0,
                "max": max(axis.max_values) if axis.max_values else 0,
                "center": (
                    sum(axis.idle_samples) / len(axis.idle_samples)
                    if axis.idle_samples else None
                ) if name == "steering" else None
            } for name, axis in self.axes.items()
        }
