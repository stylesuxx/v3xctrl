import unittest
import msgpack
from v3xctrl_control.message import Message, Latency


class TestLatency(unittest.TestCase):
    def test_roundtrip(self) -> None:
        ts = 1_987_654.0
        l = Latency(timestamp=ts)

        data = l.to_bytes()
        restored = Message.from_bytes(data)

        self.assertIsInstance(restored, Latency)
        self.assertEqual(restored.timestamp, ts)
        self.assertEqual(restored.payload, {})  # empty by design

    def test_default_constructor(self) -> None:
        l = Latency()
        self.assertEqual(l.payload, {})  # timestamp auto-set

    def test_peek_type(self) -> None:
        l = Latency()
        data = l.to_bytes()
        self.assertEqual(Message.peek_type(data), "Latency")

    def test_missing_top_level_p_raises_valueerror(self) -> None:
        l = Latency()
        obj = msgpack.unpackb(l.to_bytes())
        obj.pop("p")
        broken = msgpack.packb(obj)
        with self.assertRaises(ValueError):
            Message.from_bytes(broken)

    def test_extra_field_in_payload_raises_typeerror(self) -> None:
        l = Latency()
        obj = msgpack.unpackb(l.to_bytes())
        obj["p"]["unexpected"] = "nope"  # Latency.__init__ accepts only timestamp
        altered = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(altered)

    def test_unknown_message_type_raises(self) -> None:
        l = Latency()
        obj = msgpack.unpackb(l.to_bytes())
        obj["t"] = "NotARealType"
        bad = msgpack.packb(obj)
        with self.assertRaisesRegex(ValueError, r"Unknown message type: NotARealType"):
            Message.from_bytes(bad)

    def test_non_mapping_msgpack_raises_valueerror(self) -> None:
        non_mapping = msgpack.packb([1, 2, 3])  # top-level must be a dict
        with self.assertRaises(ValueError):
            Message.from_bytes(non_mapping)

    def test_repr_smoke(self) -> None:
        l = Latency()
        r = repr(l)
        self.assertIn("Latency", r)
        self.assertIn("payload=", r)
