import unittest
import msgpack
from v3xctrl_control.message import Message, SynAck


class TestSynAck(unittest.TestCase):
    def test_roundtrip(self) -> None:
        ts = 1_234_567.0
        sa = SynAck(timestamp=ts)

        data = sa.to_bytes()
        restored = Message.from_bytes(data)

        self.assertIsInstance(restored, SynAck)
        self.assertEqual(restored.timestamp, ts)
        self.assertEqual(restored.payload, {})  # empty payload by design

    def test_default_constructor(self) -> None:
        sa = SynAck()
        self.assertEqual(sa.payload, {})  # timestamp auto-set; payload remains empty

    def test_peek_type(self) -> None:
        sa = SynAck()
        data = sa.to_bytes()
        self.assertEqual(Message.peek_type(data), "SynAck")

    def test_missing_top_level_p_raises_valueerror(self) -> None:
        sa = SynAck()
        obj = msgpack.unpackb(sa.to_bytes())
        obj.pop("p")
        broken = msgpack.packb(obj)
        with self.assertRaises(ValueError):
            Message.from_bytes(broken)

    def test_extra_field_in_payload_raises_typeerror(self) -> None:
        sa = SynAck()
        obj = msgpack.unpackb(sa.to_bytes())
        obj["p"]["unexpected"] = "nope"  # SynAck.__init__ accepts only timestamp
        altered = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(altered)

    def test_unknown_message_type_raises(self) -> None:
        sa = SynAck()
        obj = msgpack.unpackb(sa.to_bytes())
        obj["t"] = "NotARealType"
        bad = msgpack.packb(obj)
        with self.assertRaisesRegex(ValueError, r"Unknown message type: NotARealType"):
            Message.from_bytes(bad)

    def test_non_mapping_msgpack_raises_valueerror(self) -> None:
        non_mapping = msgpack.packb([1, 2, 3])  # top-level must be a map/dict
        with self.assertRaises(ValueError):
            Message.from_bytes(non_mapping)

    def test_repr_smoke(self) -> None:
        sa = SynAck()
        r = repr(sa)
        self.assertIn("SynAck", r)
        self.assertIn("payload=", r)
