import itertools
import time
from typing import Dict, Optional, Any
from .Message import Message


class Command(Message):
    """Message type for command data."""
    _command_counter = itertools.count()

    @classmethod
    def _generate_command_id(cls) -> str:
        ts_ns = time.monotonic_ns()
        seq = next(cls._command_counter)
        return f"{ts_ns}-{seq}"

    def __init__(
        self,
        c: str,
        p: Dict[str, Any] = {},
        i: Optional[str] = None,
        timestamp: Optional[float] = None
    ) -> None:
        self.command_id = i or self._generate_command_id()

        super().__init__({
            "c": c,
            "p": p,
            "i": self.command_id
        }, timestamp)

        self.command = c
        self.parameters = p

    def get_command(self) -> str:
        return self.command

    def get_parameters(self) -> Dict[str, Any]:
        return self.parameters

    def get_command_id(self) -> str:
        return self.command_id
