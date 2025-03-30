import math
from pygame.key import ScancodeWrapper

from ui.helpers import clamp


class KeyAxisHandler:
    def __init__(self,
                 positive: int,
                 negative: int,
                 step: float = 0.02,
                 friction: float = 0.01,
                 min_val: float = -1.0,
                 max_val: float = 1.0):
        self.positive = positive
        self.negative = negative
        self.step = step
        self.friction = friction
        self.min_val = min_val
        self.max_val = max_val
        self.value = 0.0
        self.deadzone = 0.0

    def update(self, keys: ScancodeWrapper) -> None:
        if keys[self.positive]:
            self.value += self.step
        elif keys[self.negative]:
            self.value -= self.step
        else:
            if abs(self.value) < self.friction:
                self.value = 0.0
            else:
                self.value -= math.copysign(self.friction, self.value)

        value = clamp(self.value, self.min_val, self.max_val)
        self.value = 0.0 if abs(value) < self.deadzone else value

    def __repr__(self) -> str:
        return f"<KeyAxisHandler(value={self.value:.3f}, keys=({self.positive}, {self.negative}))>"
