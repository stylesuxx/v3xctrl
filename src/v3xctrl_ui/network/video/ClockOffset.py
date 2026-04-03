from v3xctrl_helper import SlidingWindowAverage


class ClockOffset:
    """
    Estimates the wall-clock difference between viewer and streamer.

    Uses round-trip Latency messages to compute the offset without relying
    on NTP. Each measurement produces:

        offset = T2 - (T1 + T4) / 2

    where T1 is the viewer send time, T2 the streamer receive time, and
    T4 the viewer receive time (all wall-clock seconds). The result tells
    us how far the streamer clock is ahead of the viewer clock.

    To convert a streamer timestamp to viewer time:
        viewer_time = streamer_time - offset

    Samples are kept in a sliding window and averaged to
    smooth out jitter from variable network latency. Older samples are
    evicted automatically on each update.
    """

    def __init__(self, window_seconds: float = 3.0) -> None:
        self._samples = SlidingWindowAverage(window_seconds)
        self._rtt: float = 0.0

    @property
    def valid(self) -> bool:
        return bool(self._samples)

    @property
    def offset_us(self) -> int:
        return int(self._samples.average)

    @property
    def rtt(self) -> float:
        return self._rtt

    def update(self, viewer_send: float, streamer_timestamp: float, viewer_receive: float) -> None:
        """
        Update offset from a round-trip measurement.

        Args:
            viewer_send: T1 - viewer send time (seconds)
            streamer_timestamp: T2 - streamer receive/send time (seconds)
            viewer_receive: T4 - viewer receive time (seconds)
        """
        offset_us = (streamer_timestamp - (viewer_send + viewer_receive) / 2) * 1_000_000
        self._samples.append(offset_us)
        self._rtt = viewer_receive - viewer_send
