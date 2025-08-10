import unittest
import msgpack
from v3xctrl_control.Message import Message, CommandAck


class TestCommandAck(unittest.TestCase):
    def test_roundtrip_and_getter(self) -> None:
        ts = 1_654_321.0
        ca = CommandAck(i="cmd-001", timestamp=ts)

        data = ca.to_bytes()
        restored = Message.from_bytes(data)

        self.assertIsInstance(restored, CommandAck)
        self.assertEqual(restored.timestamp, ts)
        self.assertEqual(restored.payload, {"i": "cmd-001"})
        self.assertEqual(restored.get_command_id(), "cmd-001")

    def test_peek_type(self) -> None:
        ca = CommandAck(i="cmd-002")
        data = ca.to_bytes()
        self.assertEqual(Message.peek_type(data), "CommandAck")

    def test_missing_required_field_i_raises_typeerror(self) -> None:
        ca = CommandAck(i="cmd-003")
        obj = msgpack.unpackb(ca.to_bytes())
        obj["p"].pop("i")
        broken = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(broken)

    def test_missing_top_level_p_raises_valueerror(self) -> None:
        ca = CommandAck(i="cmd-004")
        obj = msgpack.unpackb(ca.to_bytes())
        obj.pop("p")
        broken = msgpack.packb(obj)
        with self.assertRaises(ValueError):
            Message.from_bytes(broken)

    def test_extra_field_in_payload_raises_typeerror(self) -> None:
        ca = CommandAck(i="cmd-005")
        obj = msgpack.unpackb(ca.to_bytes())
        obj["p"]["unexpected"] = "nope"
        altered = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(altered)

    def test_unknown_message_type_raises(self) -> None:
        ca = CommandAck(i="cmd-006")
        obj = msgpack.unpackb(ca.to_bytes())
        obj["t"] = "NotARealType"
        bad = msgpack.packb(obj)
        with self.assertRaisesRegex(ValueError, r"Unknown message type: NotARealType"):
            Message.from_bytes(bad)

    def test_non_mapping_msgpack_raises_valueerror(self) -> None:
        non_mapping = msgpack.packb([1, 2, 3])  # top-level must be a dict
        with self.assertRaises(ValueError):
            Message.from_bytes(non_mapping)

    def test_repr_smoke(self) -> None:
        ca = CommandAck(i="cmd-007")
        r = repr(ca)
        self.assertIn("CommandAck", r)
        self.assertIn("payload=", r)
