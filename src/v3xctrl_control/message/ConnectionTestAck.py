from .Message import Message


class ConnectionTestAck(Message):
    def __init__(
        self,
        v: bool,
        timestamp: float | None = None
    ) -> None:
        super().__init__({
            "v": v,
        }, timestamp)

        self.valid = v

    def is_valid(self) -> bool:
        return self.valid
