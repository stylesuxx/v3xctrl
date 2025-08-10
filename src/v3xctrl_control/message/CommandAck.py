from typing import Optional
from .Message import Message


class CommandAck(Message):
    """Acknowledgment message for a Command."""

    def __init__(self, i: str, timestamp: Optional[float] = None) -> None:
        super().__init__({
            "i": i
        }, timestamp)

        self.command_id = i

    def get_command_id(self) -> str:
        return self.command_id
