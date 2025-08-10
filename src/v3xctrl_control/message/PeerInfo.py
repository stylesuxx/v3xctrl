from typing import Optional
from .Message import Message


class PeerInfo(Message):
    """Message for transmitting peer connection details (IP and ports)."""

    def __init__(
        self,
        ip: str,
        video_port: int,
        control_port: int,
        timestamp: Optional[float] = None
    ) -> None:
        super().__init__({
            "ip": ip,
            "video_port": video_port,
            "control_port": control_port,
        }, timestamp)

        self.ip = ip
        self.video_port = video_port
        self.control_port = control_port

    def get_ip(self) -> str:
        return self.ip

    def get_video_port(self) -> int:
        return self.video_port

    def get_control_port(self) -> int:
        return self.control_port
