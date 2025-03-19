class UDPPacket():
    def __init__(self, data: bytes, host: str, port: int):
        self.data = data
        self.host = host
        self.port = port
