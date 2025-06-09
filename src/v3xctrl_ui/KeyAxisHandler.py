from collections import deque
from pygame.key import ScancodeWrapper
from v3xctrl_helper import clamp


class KeyAxisHandler:
    def __init__(self,
                 positive: int,
                 negative: int,
                 friction: float = 0.03,
                 max_step: float = 0.10,
                 hold_ramp_frames: int = 10,
                 hold_interval: int = 25,
                 min_tap_interval: int = 3,
                 avg_window: int = 8,
                 centering_multiplier: float = 4.0,
                 min_val: float = -1.0,
                 max_val: float = 1.0,
                 deadzone: float = 0.0,
                 cooldown_frames: int = 3):
        self.positive = positive
        self.negative = negative
        self.friction = friction
        self.max_step = max_step
        self.hold_ramp_frames = hold_ramp_frames
        self.hold_interval = hold_interval
        self.min_tap_interval = min_tap_interval
        self.avg_window = avg_window
        self.centering_multiplier = centering_multiplier
        self.min_val = min_val
        self.max_val = max_val
        self.deadzone = deadzone
        self.cooldown_frames = cooldown_frames

        self.value = 0.0
        self.cooldown = 0
        self.frames_since_last_tap = hold_interval
        self.last_direction = 0
        self.last_tap_intervals = deque([hold_interval] * avg_window, maxlen=avg_window)

        self.holding = False
        self.hold_frames = 0

    def _smoothed_interval(self) -> float:
        return sum(self.last_tap_intervals) / len(self.last_tap_intervals)

    def _hold_step(self) -> float:
        progress = clamp(self.hold_frames / self.hold_ramp_frames, 0.0, 1.0)
        return self.friction + (self.max_step - self.friction) * progress

    def update(self, keys: ScancodeWrapper) -> float:
        key_pressed = False
        direction = 0

        if keys[self.positive] and not keys[self.negative]:
            direction = 1
        elif keys[self.negative] and not keys[self.positive]:
            direction = -1

        # Reset on direction change
        if direction != 0 and direction != self.last_direction:
            self.value = 0.0
            self.frames_since_last_tap = self.hold_interval
            self.hold_frames = 0
            self.last_direction = direction

        if direction != 0:
            key_pressed = True

            if self.frames_since_last_tap >= self.min_tap_interval:
                # Tap
                self.last_tap_intervals.append(self.frames_since_last_tap)

                ideal = max(1.0, self._smoothed_interval())
                actual = self.frames_since_last_tap
                delta = actual - ideal
                adjust = clamp(-delta / ideal, -1.0, 1.0)

                step = direction * self.friction * (1.0 + adjust)
                self.value += step
                self.value -= direction * self.friction  # cancel base friction at sweet spot

                self.frames_since_last_tap = 0
                self.cooldown = self.cooldown_frames
                self.holding = False
                self.hold_frames = 0
            else:
                # Hold
                self.hold_frames += 1
                self.value += direction * self._hold_step()
                self.cooldown = self.cooldown_frames
                self.holding = True
        else:
            # No key pressed
            self.frames_since_last_tap += 1
            self.hold_frames = 0
            self.holding = False

            if self.cooldown > 0:
                self.cooldown -= 1
            else:
                decay = self.friction * self.centering_multiplier
                if self.value > 0:
                    self.value = max(0.0, self.value - decay)
                elif self.value < 0:
                    self.value = min(0.0, self.value + decay)

        # Clamp and apply deadzone
        self.value = clamp(self.value, self.min_val, self.max_val)
        if abs(self.value) < self.deadzone:
            self.value = 0.0

        return self.value

    def __repr__(self) -> str:
        avg = self._smoothed_interval()
        return (f"<KeyAxisHandler(value={self.value:.3f}, cooldown={self.cooldown}, "
                f"tap_avg_interval={avg:.1f}, hold_frames={self.hold_frames}, "
                f"keys=({self.positive}, {self.negative}))>")
