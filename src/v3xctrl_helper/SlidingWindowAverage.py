import time
from collections import deque


class SlidingWindowAverage:
    """
    Time-based sliding window that averages numeric samples.

    Samples older than window_seconds are evicted automatically on each
    append. Useful for smoothing noisy measurements like latency or
    clock offset over a fixed time horizon.
    """

    def __init__(self, window_seconds: float) -> None:
        self._window_seconds = window_seconds
        self._samples: deque[tuple[float, float]] = deque()

    @property
    def average(self) -> float:
        if not self._samples:
            return 0.0

        return sum(s[1] for s in self._samples) / len(self._samples)

    def append(self, value: float) -> None:
        now = time.monotonic()
        self._samples.append((now, value))
        self._evict(now)

    def clear(self) -> None:
        self._samples.clear()

    def _evict(self, now: float) -> None:
        cutoff = now - self._window_seconds
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def __len__(self) -> int:
        return len(self._samples)

    def __bool__(self) -> bool:
        return len(self._samples) > 0
