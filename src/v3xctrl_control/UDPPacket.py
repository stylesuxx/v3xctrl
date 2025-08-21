import time


class UDPPacket():
    """
    Use time.time for inter system checks - this would obviously require the
    clocks on both systems to be synchronized, by for example using the same NTP
    server.
    """
    def __init__(self, data: bytes, host: str, port: int) -> None:
        self.data = data
        self.host = host
        self.port = port

        self.timestamp = time.time()
