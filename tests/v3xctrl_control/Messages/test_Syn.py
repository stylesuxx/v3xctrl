import unittest
import msgpack
from v3xctrl_control.Message import Message, Syn


class TestSyn(unittest.TestCase):
    def test_roundtrip_and_getters(self) -> None:
        ts = 1_654_321.0
        s = Syn(v=2, timestamp=ts)

        data = s.to_bytes()
        restored = Message.from_bytes(data)

        self.assertIsInstance(restored, Syn)
        self.assertEqual(restored.timestamp, ts)
        self.assertEqual(restored.payload, {"v": 2})
        self.assertEqual(restored.get_version(), 2)

    def test_default_version(self) -> None:
        s = Syn()
        self.assertEqual(s.get_version(), 1)
        self.assertEqual(s.payload, {"v": 1})

    def test_peek_type(self) -> None:
        s = Syn(v=3)
        data = s.to_bytes()
        self.assertEqual(Message.peek_type(data), "Syn")

    def test_missing_top_level_p_raises_valueerror(self) -> None:
        s = Syn(v=2)
        obj = msgpack.unpackb(s.to_bytes())
        obj.pop("p")  # remove payload wrapper
        broken = msgpack.packb(obj)
        with self.assertRaises(ValueError):
            Message.from_bytes(broken)

    def test_extra_field_in_payload_raises_typeerror(self) -> None:
        s = Syn(v=2)
        obj = msgpack.unpackb(s.to_bytes())
        obj["p"]["unexpected"] = "nope"  # ctor doesn't accept this kwarg
        altered = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(altered)

    def test_unknown_message_type_raises(self) -> None:
        s = Syn(v=2)
        obj = msgpack.unpackb(s.to_bytes())
        obj["t"] = "NotARealType"
        bad = msgpack.packb(obj)
        with self.assertRaisesRegex(ValueError, r"Unknown message type: NotARealType"):
            Message.from_bytes(bad)

    def test_non_mapping_msgpack_raises_valueerror(self) -> None:
        non_mapping = msgpack.packb([1, 2, 3])  # top-level is not a dict
        with self.assertRaises(ValueError):
            Message.from_bytes(non_mapping)

    def test_repr_smoke(self) -> None:
        s = Syn(v=5)
        r = repr(s)
        self.assertIn("Syn", r)
        self.assertIn("payload=", r)
