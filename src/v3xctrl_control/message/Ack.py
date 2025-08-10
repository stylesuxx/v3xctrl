from typing import Optional
from .Message import Message


class Ack(Message):
    def __init__(self, timestamp: Optional[float] = None) -> None:
        super().__init__({}, timestamp)
