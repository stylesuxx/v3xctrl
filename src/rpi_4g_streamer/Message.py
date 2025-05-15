"""
Short keys are used here on purpose in order to save space when packing the
messages. Still, the attributes of the classes are descriptive and this is the
only part the devs need to interact with, so this should not be too confusing.
"""

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
        self.timestamp = time.time() if timestamp is None else timestamp
        self.payload = payload

    def to_bytes(self) -> bytes:
        """Serialize the message to bytes using msgpack."""
        return msgpack.packb({
            "t": self.type,
            "p": self.payload,
            "d": self.timestamp,
        })

    @classmethod
    def from_bytes(cls, data: bytes):
        """Dynamically deserialize bytes into the correct message subclass."""
        try:
            obj = msgpack.unpackb(data)
            msg_type = obj["t"]
            timestamp = obj["d"]
            payload = obj["p"]
        except (KeyError, TypeError, msgpack.exceptions.ExtraData) as e:
            raise ValueError("Malformed message payload") from e

        if msg_type in cls._registry:
            return cls._registry[msg_type](**payload, timestamp=timestamp)
        else:
            raise ValueError(f"Unknown message type: {msg_type}")

    @property
    def type(self) -> str:
        return self.__class__.__name__

    def __repr__(self):
        return f"{self.type}(payload={self.payload}, timestamp={self.timestamp})"


class Telemetry(Message):
    """Message type for telemetry data."""

    def __init__(self, v: dict = None, timestamp: float = None):
        if v is None:
            v = {}

        super().__init__({
            "v": v
        }, timestamp)

        self.values = v

    def get_values(self) -> dict:
        return self.values


class Control(Message):
    """Message type for telemetry data."""

    def __init__(self, v: dict = None, timestamp: float = None):
        if v is None:
            v = {}

        super().__init__({
            "v": v
        }, timestamp)

        self.values = v

    def get_values(self) -> dict:
        return self.values


class Syn(Message):
    def __init__(self, timestamp: float = None):
        super().__init__({}, timestamp)


class Ack(Message):
    def __init__(self, timestamp: float = None):
        super().__init__({}, timestamp)


class Latency(Message):
    def __init__(self, timestamp: float = None):
        super().__init__({}, timestamp)


class Command(Message):
    """Message type for command data."""

    def __init__(self, c: str, timestamp: float = None):
        super().__init__({
            "c": c
        }, timestamp)

        self.value = c


class Heartbeat(Message):
    def __init__(self, timestamp: float = None):
        super().__init__({}, timestamp)


"""
Message types used for UDP hole punching
"""


class PeerAnnouncement(Message):
    def __init__(self, r: str, i: str, p: str, timestamp: float = None):
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


class PeerInfo(Message):
    """Message for transmitting peer connection details (IP and ports)."""

    def __init__(self, ip: str, video_port: int, control_port: int, timestamp: float = None):
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
