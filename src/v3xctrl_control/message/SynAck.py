from .Message import Message


class SynAck(Message):
    def __init__(self, timestamp: float | None = None) -> None:
        super().__init__({}, timestamp)
