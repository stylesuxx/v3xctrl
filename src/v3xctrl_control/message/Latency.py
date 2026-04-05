from .Message import Message


class Latency(Message):
    """Round-trip latency measurement between viewer and streamer.

    Used for two purposes:
    1. RTT display - the OSD shows RTT/2 as a one-way latency estimate.
    2. Clock offset estimation - lets the viewer align its clock with the
       streamer's without relying on NTP.

    Protocol:
        1. Viewer sends Latency(timestamp=T1) where T1 = viewer wall clock.
        2. Streamer receives, responds with Latency(timestamp=T1, st=T2)
           where T2 = streamer wall clock at receive time.
        3. Viewer receives the response at T4 (viewer wall clock) and computes:
           - RTT = T4 - T1
           - clock_offset = T2 - (T1 + T4) / 2

    The clock offset converts streamer timestamps to viewer time:
        viewer_time = streamer_time - clock_offset

    When st is None, the message is a request from the viewer.
    When st is set, it is the streamer's response.
    """

    def __init__(self, st: float | None = None, timestamp: float | None = None) -> None:
        payload: dict[str, float] = {}
        if st is not None:
            payload["st"] = st
        super().__init__(payload, timestamp)
        self.streamer_timestamp = st
