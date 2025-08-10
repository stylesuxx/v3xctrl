import unittest
import msgpack
from typing import Dict, Any, Set
from v3xctrl_control.Message import Message, Command


class TestCommand(unittest.TestCase):
    def test_roundtrip_and_getters(self) -> None:
        ts = 1_701_234.0
        params: Dict[str, Any] = {"speed": "fast", "priority": 3}
        cmd = Command(c="start", p=params, i="cmd-001", timestamp=ts)

        data = cmd.to_bytes()
        restored = Message.from_bytes(data)

        self.assertIsInstance(restored, Command)
        self.assertEqual(restored.timestamp, ts)

        # getters
        self.assertEqual(restored.get_command(), "start")
        self.assertEqual(restored.get_parameters(), params)
        self.assertEqual(restored.get_command_id(), "cmd-001")

        # serialized payload shape
        self.assertEqual(restored.payload, {"c": "start", "p": params, "i": "cmd-001"})

    def test_explicit_id_preserved(self) -> None:
        cmd = Command(c="calibrate", p={"level": 2}, i="my-id-42")
        data = cmd.to_bytes()
        restored = Message.from_bytes(data)
        self.assertEqual(restored.get_command_id(), "my-id-42")
        self.assertEqual(restored.payload["i"], "my-id-42")

    def test_auto_generated_id_format_and_uniqueness(self) -> None:
        ids: Set[str] = set()
        for _ in range(5):
            c = Command(c="noop")
            cid = c.get_command_id()
            # monotonic_ns-seq format like "<ns>-<seq>"
            self.assertIn("-", cid)
            left, right = cid.split("-", 1)
            self.assertTrue(left.isdigit())
            self.assertTrue(right.isdigit())
            ids.add(cid)

        # should all be unique
        self.assertEqual(len(ids), 5)

        # roundtrip keeps auto id
        c0 = Command(c="noop")
        restored = Message.from_bytes(c0.to_bytes())
        self.assertEqual(restored.get_command_id(), c0.get_command_id())

    def test_peek_type(self) -> None:
        c = Command(c="stop")
        data = c.to_bytes()
        self.assertEqual(Message.peek_type(data), "Command")

    def test_missing_required_field_c_raises_typeerror(self) -> None:
        c = Command(c="ping", p={"x": 1})
        obj = msgpack.unpackb(c.to_bytes())
        # remove required ctor kwarg "c"
        obj["p"].pop("c")
        broken = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(broken)

    def test_missing_top_level_p_raises_valueerror(self) -> None:
        c = Command(c="ping")
        obj = msgpack.unpackb(c.to_bytes())
        obj.pop("p")  # Message.from_bytes expects top-level 'p'
        broken = msgpack.packb(obj)
        with self.assertRaises(ValueError):
            Message.from_bytes(broken)

    def test_extra_field_in_payload_raises_typeerror(self) -> None:
        c = Command(c="ping")
        obj = msgpack.unpackb(c.to_bytes())
        # inject unknown kwarg for Command.__init__(...)
        obj["p"]["unexpected"] = "nope"
        altered = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(altered)

    def test_unknown_message_type_raises(self) -> None:
        c = Command(c="ping")
        obj = msgpack.unpackb(c.to_bytes())
        obj["t"] = "NotARealType"
        bad = msgpack.packb(obj)
        with self.assertRaisesRegex(ValueError, r"Unknown message type: NotARealType"):
            Message.from_bytes(bad)

    def test_non_mapping_msgpack_raises_valueerror(self) -> None:
        non_mapping = msgpack.packb([1, 2, 3])  # top-level must be a dict
        with self.assertRaises(ValueError):
            Message.from_bytes(non_mapping)
