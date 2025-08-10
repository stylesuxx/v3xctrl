# tests/v3xctrl_control/message/test_Error.py
import unittest
import msgpack
from v3xctrl_control.message import Message, Error


class TestError(unittest.TestCase):
    def test_roundtrip_and_getter(self) -> None:
        ts = 1_555_444.0
        err = Error(e="Something went wrong", timestamp=ts)

        data = err.to_bytes()
        restored = Message.from_bytes(data)

        self.assertIsInstance(restored, Error)
        self.assertEqual(restored.timestamp, ts)
        self.assertEqual(restored.payload, {"e": "Something went wrong"})
        self.assertEqual(restored.get_error(), "Something went wrong")

    def test_peek_type(self) -> None:
        err = Error(e="Network failure")
        data = err.to_bytes()
        self.assertEqual(Message.peek_type(data), "Error")

    def test_missing_required_field_raises_typeerror(self) -> None:
        err = Error(e="Bad stuff")
        obj = msgpack.unpackb(err.to_bytes())
        obj["p"].pop("e")  # remove required kwarg
        broken = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(broken)

    def test_missing_top_level_p_raises_valueerror(self) -> None:
        err = Error(e="Bad stuff")
        obj = msgpack.unpackb(err.to_bytes())
        obj.pop("p")
        broken = msgpack.packb(obj)
        with self.assertRaises(ValueError):
            Message.from_bytes(broken)

    def test_extra_field_in_payload_raises_typeerror(self) -> None:
        err = Error(e="Bad stuff")
        obj = msgpack.unpackb(err.to_bytes())
        obj["p"]["unexpected"] = "nope"
        altered = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(altered)

    def test_unknown_message_type_raises(self) -> None:
        err = Error(e="Bad stuff")
        obj = msgpack.unpackb(err.to_bytes())
        obj["t"] = "NotARealType"
        bad = msgpack.packb(obj)
        with self.assertRaisesRegex(ValueError, r"Unknown message type: NotARealType"):
            Message.from_bytes(bad)

    def test_non_mapping_msgpack_raises_valueerror(self) -> None:
        non_mapping = msgpack.packb([1, 2, 3])
        with self.assertRaises(ValueError):
            Message.from_bytes(non_mapping)

    def test_repr_smoke(self) -> None:
        err = Error(e="Bad stuff")
        r = repr(err)
        self.assertIn("Error", r)
        self.assertIn("payload=", r)
