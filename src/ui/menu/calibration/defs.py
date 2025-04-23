from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List


class CalibrationStage(Enum):
    STEERING = "steering"
    STEERING_CENTER = "steering_center"
    THROTTLE = "throttle"
    BRAKE = "brake"


class CalibratorState(Enum):
    PAUSE = auto()
    ACTIVE = auto()
    COMPLETE = auto()


@dataclass
class AxisCalibrationData:
    axis: Optional[int] = None
    baseline: Optional[List[float]] = None
    detection_frames: int = 0
    max_values: List[float] = field(default_factory=list)
    max_last: Optional[float] = None
    max_stable: int = 0
    idle_last: Optional[float] = None
    idle_stable: int = 0
    idle_samples: List[float] = field(default_factory=list)
