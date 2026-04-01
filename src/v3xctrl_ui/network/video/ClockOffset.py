class ClockOffset:
    """Tracks clock offset between viewer and streamer using round-trip measurements."""

    def __init__(self) -> None:
        self._offset_us: int = 0
        self._rtt: float = 0.0
        self._valid: bool = False

    @property
    def valid(self) -> bool:
        return self._valid

    @property
    def offset_us(self) -> int:
        return self._offset_us

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
        self._offset_us = int((streamer_timestamp - (viewer_send + viewer_receive) / 2) * 1_000_000)
        self._rtt = viewer_receive - viewer_send
        self._valid = True
