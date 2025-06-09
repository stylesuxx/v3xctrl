import math
from pygame.key import ScancodeWrapper
from v3xctrl_helper import clamp


class KeyAxisHandler:
    def __init__(self,
                 positive: int,
                 negative: int,
                 smoothing: float = 0.05,
                 min_val: float = -1.0,
                 max_val: float = 1.0,
                 deadzone: float = 0.0,
                 step: float = 0.0,
                 friction: float = 0.0):
        self.positive = positive
        self.negative = negative
        self.smoothing = smoothing
        self.min_val = min_val
        self.max_val = max_val
        self.deadzone = deadzone

        self.target = 0.0
        self.value = 0.0

    def update(self, keys: ScancodeWrapper) -> float:
        # Determine target based on key states
        if keys[self.positive] and not keys[self.negative]:
            self.target = 1.0
        elif keys[self.negative] and not keys[self.positive]:
            self.target = -1.0
        else:
            self.target = 0.0

        # Easing toward target
        delta = self.target - self.value
        self.value += delta * self.smoothing

        # Clamp and apply deadzone
        value = clamp(self.value, self.min_val, self.max_val)
        self.value = 0.0 if abs(value) < self.deadzone else value

        return self.value

    def __repr__(self) -> str:
        return f"<KeyAxisHandler(value={self.value:.3f}, target={self.target:.3f}, keys=({self.positive}, {self.negative}))>"
