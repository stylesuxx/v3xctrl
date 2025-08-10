from typing import Optional
from .Message import Message


class PeerAnnouncement(Message):
    def __init__(
        self,
        r: str,
        i: str,
        p: str,
        timestamp: Optional[float] = None
    ) -> None:
        super().__init__({
            "r": r,
            "i": i,
            "p": p,
        }, timestamp)

        self.role = r
        self.id = i
        self.port_type = p

    def get_role(self) -> str:
        return self.role

    def get_id(self) -> str:
        return self.id

    def get_port_type(self) -> str:
        return self.port_type
