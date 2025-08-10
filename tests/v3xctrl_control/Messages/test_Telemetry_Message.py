import unittest
import msgpack
from typing import Dict, Any
from v3xctrl_control.message import Message, Telemetry


class TestTelemetry(unittest.TestCase):
    def test_roundtrip_and_getters(self) -> None:
        ts = 1_734_567.0
        payload: Dict[str, Any] = {"fps": 30, "temp_c": 52.5, "load": {"cpu": 0.42, "gpu": 0.15}}
        t = Telemetry(v=payload, timestamp=ts)

        data = t.to_bytes()
        restored = Message.from_bytes(data)

        self.assertIsInstance(restored, Telemetry)
        self.assertEqual(restored.timestamp, ts)
        # full payload wrapper preserved
        self.assertEqual(restored.payload, {"v": payload})
        # getter returns inner dict
        self.assertEqual(restored.get_values(), payload)

    def test_peek_type(self) -> None:
        t = Telemetry(v={"a": 1})
        data = t.to_bytes()
        self.assertEqual(Message.peek_type(data), "Telemetry")

    def test_missing_top_level_p_raises_valueerror(self) -> None:
        t = Telemetry(v={"x": 1})
        obj = msgpack.unpackb(t.to_bytes())
        # Remove top-level 'p' so Message.from_bytes() cannot find payload
        obj.pop("p")
        broken = msgpack.packb(obj)
        with self.assertRaises(ValueError):
            Message.from_bytes(broken)

    def test_extra_field_in_payload_raises_typeerror(self) -> None:
        t = Telemetry(v={"x": 1})
        obj = msgpack.unpackb(t.to_bytes())
        # Inject an unexpected kwarg into the ctor
        obj["p"]["unexpected"] = "nope"
        altered = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(altered)

    def test_unknown_message_type_raises(self) -> None:
        t = Telemetry(v={"x": 1})
        obj = msgpack.unpackb(t.to_bytes())
        obj["t"] = "NotARealType"
        bad = msgpack.packb(obj)
        with self.assertRaisesRegex(ValueError, r"Unknown message type: NotARealType"):
            Message.from_bytes(bad)

    def test_non_mapping_msgpack_raises_valueerror(self) -> None:
        # Not a dict at the top level -> 'msg["t"]' will raise TypeError,
        # which is wrapped as ValueError("Malformed message payload")
        non_mapping = msgpack.packb([1, 2, 3])
        with self.assertRaises(ValueError):
            Message.from_bytes(non_mapping)

    def test_empty_constructor_defaults(self) -> None:
        # Ensure default ctor works and wraps empty dict under 'v'
        t = Telemetry()
        self.assertEqual(t.get_values(), {})
        self.assertEqual(t.payload, {"v": {}})
