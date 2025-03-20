import abc
import time
import msgpack


class Message(abc.ABC):
    """Abstract Base Class for all messages with built-in serialization."""

    _registry = {}

    def __init_subclass__(cls, **kwargs):
        """Automatically register subclasses using their class name."""
        Message._registry[cls.__name__] = cls

    def __init__(self, payload: dict, timestamp: float = None):
        """Initialize message with a dictionary payload."""
        self.timestamp = timestamp
        if not self.timestamp:
            self.timestamp = time.time()
        self.payload = payload

    def to_bytes(self) -> bytes:
        """Serialize the message to bytes using msgpack."""
        return msgpack.packb({
            "t": self.__class__.__name__,
            "p": self.payload,
            "d": self.timestamp,
        })

    @classmethod
    def from_bytes(cls, data: bytes):
        """Dynamically deserialize bytes into the correct message subclass."""
        obj = msgpack.unpackb(data)
        msg_type = obj["t"]
        timestamp = obj["d"]
        payload = obj["p"]

        if msg_type in cls._registry:
            return cls._registry[msg_type](**payload, timestamp=timestamp)
        else:
            raise ValueError(f"Unknown message type: {msg_type}")

    def __repr__(self):
        return f"{self.__class__.__name__}(payload={self.payload}, timestamp={self.timestamp})"


class Telemetry(Message):
    """Message type for telemetry data."""

    def __init__(self, values: dict = {}, timestamp: float = None):
        super().__init__(values, timestamp)

        self.value = values


class Control(Message):
    """Message type for telemetry data."""

    def __init__(self, values: dict = {}, timestamp: float = None):
        super().__init__(values, timestamp)

        self.value = values


class Syn(Message):
    def __init__(self, timestamp: float = None):
        super().__init__({}, timestamp)


class Ack(Message):
    def __init__(self, timestamp: float = None):
        super().__init__({}, timestamp)


class Command(Message):
    """Message type for command data."""

    def __init__(self, command: str, timestamp: float = None):
        super().__init__({
            "cmd": command
        }, timestamp)

        self.value = command


class Heartbeat(Message):
    def __init__(self, timestamp: float = None):
        super().__init__({}, timestamp)
