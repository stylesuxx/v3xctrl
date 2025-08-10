from typing import Optional
from .Message import Message


class Error(Message):
    def __init__(self, e: str, timestamp: Optional[float] = None) -> None:
        super().__init__({
            "e": e,
        }, timestamp)

        self.error = e

    def get_error(self) -> str:
        return self.error
