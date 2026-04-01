from .Message import Message


class Latency(Message):
    def __init__(self, streamer_timestamp: float | None = None, timestamp: float | None = None) -> None:
        payload: dict[str, float] = {}
        if streamer_timestamp is not None:
            payload["streamer_timestamp"] = streamer_timestamp
        super().__init__(payload, timestamp)
        self.streamer_timestamp = streamer_timestamp
