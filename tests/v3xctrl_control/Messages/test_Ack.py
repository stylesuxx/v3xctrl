import unittest
import msgpack
from v3xctrl_control.Message import Message, Ack


class TestAck(unittest.TestCase):
    def test_roundtrip(self) -> None:
        ts = 1_111_222.0
        a = Ack(timestamp=ts)

        data = a.to_bytes()
        restored = Message.from_bytes(data)

        self.assertIsInstance(restored, Ack)
        self.assertEqual(restored.timestamp, ts)
        self.assertEqual(restored.payload, {})  # empty payload by design

    def test_default_constructor(self) -> None:
        a = Ack()
        self.assertEqual(a.payload, {})  # still empty; timestamp is set automatically

    def test_peek_type(self) -> None:
        a = Ack()
        data = a.to_bytes()
        self.assertEqual(Message.peek_type(data), "Ack")

    def test_missing_top_level_p_raises_valueerror(self) -> None:
        a = Ack()
        obj = msgpack.unpackb(a.to_bytes())
        obj.pop("p")
        broken = msgpack.packb(obj)
        with self.assertRaises(ValueError):
            Message.from_bytes(broken)

    def test_extra_field_in_payload_raises_typeerror(self) -> None:
        a = Ack()
        obj = msgpack.unpackb(a.to_bytes())
        obj["p"]["unexpected"] = "nope"  # Ack.__init__ accepts only timestamp
        altered = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(altered)

    def test_unknown_message_type_raises(self) -> None:
        a = Ack()
        obj = msgpack.unpackb(a.to_bytes())
        obj["t"] = "NotARealType"
        bad = msgpack.packb(obj)
        with self.assertRaisesRegex(ValueError, r"Unknown message type: NotARealType"):
            Message.from_bytes(bad)

    def test_non_mapping_msgpack_raises_valueerror(self) -> None:
        non_mapping = msgpack.packb([1, 2, 3])  # top-level must be a map
        with self.assertRaises(ValueError):
            Message.from_bytes(non_mapping)

    def test_repr_smoke(self) -> None:
        a = Ack()
        r = repr(a)
        self.assertIn("Ack", r)
        self.assertIn("payload=", r)
