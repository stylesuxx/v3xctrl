from typing import Dict, List

from v3xctrl_ui.menu.calibration.defs import CalibrationStage


class CalibrationSteps:
    """Static class for managing calibration steps"""

    STEP_LABELS: Dict[CalibrationStage, str] = {
        CalibrationStage.STEERING: "Move the steering axis to its left and right maxima...",
        CalibrationStage.STEERING_CENTER: "Let go of steering to detect center position...",
        CalibrationStage.THROTTLE: "Move the throttle axis to its minimum and maximum positions...",
        CalibrationStage.BRAKE: "Move the brake axis to its minimum and maximum positions..."
    }

    STEP_ORDER: List[CalibrationStage] = list(STEP_LABELS.keys())

    @staticmethod
    def get_label(stage: CalibrationStage) -> str:
        return CalibrationSteps.STEP_LABELS.get(stage, "")
