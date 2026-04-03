import time


class ClockOffset:
    """Tracks clock offset between viewer and streamer using round-trip measurements."""

    def __init__(self, window_seconds: float = 5.0) -> None:
        self._window_seconds = window_seconds
        self._samples: list[tuple[float, int]] = []
        self._rtt: float = 0.0

    @property
    def valid(self) -> bool:
        return len(self._samples) > 0

    @property
    def offset_us(self) -> int:
        if not self._samples:
            return 0
        return sum(s[1] for s in self._samples) // len(self._samples)

    @property
    def rtt(self) -> float:
        return self._rtt

    def update(self, viewer_send: float, streamer_timestamp: float, viewer_receive: float) -> None:
        """Update offset from a round-trip measurement.

        Args:
            viewer_send: T1 - viewer send time (seconds)
            streamer_timestamp: T2 - streamer receive/send time (seconds)
            viewer_receive: T4 - viewer receive time (seconds)
        """
        now = time.monotonic()
        offset_us = int((streamer_timestamp - (viewer_send + viewer_receive) / 2) * 1_000_000)
        self._samples.append((now, offset_us))
        self._rtt = viewer_receive - viewer_send
        self._evict(now)

    def _evict(self, now: float) -> None:
        cutoff = now - self._window_seconds
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.pop(0)
