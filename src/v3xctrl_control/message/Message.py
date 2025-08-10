"""
Short keys are used here on purpose in order to save space when packing the
messages. Still, the attributes of the classes are descriptive and this is the
only part the devs need to interact with, so this should not be too confusing.
"""

import abc
import time
import msgpack
from typing import Any, Dict, Optional, TypedDict, cast


class MessageDict(TypedDict):
    t: str
    p: Dict[str, object]
    d: float


class Message(abc.ABC):
    """Abstract Base Class for all messages with built-in serialization."""

    _registry: Dict[str, Any] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Automatically register subclasses using their class name."""
        Message._registry[cls.__name__] = cls

    def __init__(
        self,
        payload: Dict[str, Any],
        timestamp: Optional[float] = None
    ) -> None:
        """Initialize message with a dictionary payload."""
        self.timestamp = time.time() if timestamp is None else timestamp
        self.payload = payload

    def to_bytes(self) -> bytes:
        """Serialize the message to bytes using msgpack."""
        msg: MessageDict = {
            "t": self.type,
            "p": self.payload,
            "d": self.timestamp,
        }
        return msgpack.packb(msg)  # type: ignore[no-untyped-call]

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        """Dynamically deserialize bytes into the correct message subclass."""
        try:
            msg: MessageDict = cast(MessageDict, msgpack.unpackb(data))  # type: ignore[arg-type]
            msg_type: str = msg["t"]
            timestamp = msg["d"]
            payload = msg["p"]
        except (KeyError, TypeError, msgpack.exceptions.ExtraData) as e:
            raise ValueError("Malformed message payload") from e

        if msg_type in cls._registry:
            return cls._registry[msg_type](**payload, timestamp=timestamp)
        else:
            raise ValueError(f"Unknown message type: {msg_type}")

    @property
    def type(self) -> str:
        return self.__class__.__name__

    def __repr__(self) -> str:
        return f"{self.type}(payload={self.payload}, timestamp={self.timestamp})"

    @staticmethod
    def peek_type(data: bytes) -> str:
        try:
            obj = cast(MessageDict, msgpack.unpackb(data, strict_map_key=False))  # type: ignore[arg-type]
            return obj.get("t", "Unknown")
        except Exception:
            return "Unknown"
