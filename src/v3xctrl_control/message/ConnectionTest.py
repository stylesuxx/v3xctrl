from .Message import Message


class ConnectionTest(Message):
    def __init__(
        self,
        i: str,
        s: bool = False,
        timestamp: float | None = None
    ) -> None:
        super().__init__({
            "i": i,
            "s": s,
        }, timestamp)

        self.id = i
        self.spectator = s

    def get_id(self) -> str:
        return self.id

    def is_spectator(self) -> bool:
        return self.spectator
