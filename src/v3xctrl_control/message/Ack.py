from .Message import Message


class Ack(Message):
    def __init__(self, timestamp: float | None = None) -> None:
        super().__init__({}, timestamp)
