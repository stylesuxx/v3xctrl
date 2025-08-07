import time


class UDPPacket():
    def __init__(self, data: bytes, host: str, port: int) -> None:
        self.data = data
        self.host = host
        self.port = port

        self.timestamp = time.monotonic()
