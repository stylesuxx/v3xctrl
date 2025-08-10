import unittest
import msgpack
from typing import Dict, Any
from v3xctrl_control.message import Message, Control


class TestControl(unittest.TestCase):
    def test_roundtrip_and_getters(self) -> None:
        ts = 1_777_888.0
        payload: Dict[str, Any] = {"steering": -0.5, "throttle": 0.8}
        ctrl = Control(v=payload, timestamp=ts)

        data = ctrl.to_bytes()
        restored = Message.from_bytes(data)

        self.assertIsInstance(restored, Control)
        self.assertEqual(restored.timestamp, ts)
        # full payload wrapper
        self.assertEqual(restored.payload, {"v": payload})
        # getter returns inner dict
        self.assertEqual(restored.get_values(), payload)

    def test_default_constructor(self) -> None:
        ctrl = Control()
        self.assertEqual(ctrl.get_values(), {})
        self.assertEqual(ctrl.payload, {"v": {}})

    def test_peek_type(self) -> None:
        ctrl = Control(v={"x": 1})
        data = ctrl.to_bytes()
        self.assertEqual(Message.peek_type(data), "Control")

    def test_missing_top_level_p_raises_valueerror(self) -> None:
        ctrl = Control(v={"x": 1})
        obj = msgpack.unpackb(ctrl.to_bytes())
        obj.pop("p")
        broken = msgpack.packb(obj)
        with self.assertRaises(ValueError):
            Message.from_bytes(broken)

    def test_extra_field_in_payload_raises_typeerror(self) -> None:
        ctrl = Control(v={"x": 1})
        obj = msgpack.unpackb(ctrl.to_bytes())
        obj["p"]["unexpected"] = "nope"
        altered = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(altered)

    def test_unknown_message_type_raises(self) -> None:
        ctrl = Control(v={"x": 1})
        obj = msgpack.unpackb(ctrl.to_bytes())
        obj["t"] = "NotARealType"
        bad = msgpack.packb(obj)
        with self.assertRaisesRegex(ValueError, r"Unknown message type: NotARealType"):
            Message.from_bytes(bad)

    def test_non_mapping_msgpack_raises_valueerror(self) -> None:
        non_mapping = msgpack.packb([1, 2, 3])
        with self.assertRaises(ValueError):
            Message.from_bytes(non_mapping)

    def test_repr_smoke(self) -> None:
        ctrl = Control(v={"a": 1})
        r = repr(ctrl)
        self.assertIn("Control", r)
        self.assertIn("payload=", r)
