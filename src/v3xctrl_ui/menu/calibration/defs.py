from enum import Enum, auto
from dataclasses import dataclass, field


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
    axis: int | None = None
    baseline: list[float] | None = None
    detection_start: float | None = None

    max_values: list[float] = field(default_factory=list[float])

    max_last: float | None = None
    max_stable_since: float | None = None

    min_last: float | None = None
    min_stable_since: float | None = None

    idle_last: float | None = None
    idle_stable_since: float | None = None
    idle_samples: list[float] = field(default_factory=list[float])
