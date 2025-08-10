from typing import Optional
from .Message import Message


class Syn(Message):
    def __init__(self, v: int = 1, timestamp: Optional[float] = None) -> None:
        super().__init__({
            "v": v
        }, timestamp)

        self.version = v

    def get_version(self) -> int:
        return self.version
