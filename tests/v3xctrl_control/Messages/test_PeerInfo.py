import unittest
import msgpack
from v3xctrl_control.message import Message, PeerInfo


class TestPeerInfo(unittest.TestCase):
    def test_roundtrip_and_getters(self) -> None:
        ts = 1_654_987.0
        pi = PeerInfo(ip="192.168.0.50", video_port=1000, control_port=2000, timestamp=ts)

        data = pi.to_bytes()
        restored = Message.from_bytes(data)

        self.assertIsInstance(restored, PeerInfo)
        self.assertEqual(restored.timestamp, ts)

        # Check getters
        self.assertEqual(restored.get_ip(), "192.168.0.50")
        self.assertEqual(restored.get_video_port(), 1000)
        self.assertEqual(restored.get_control_port(), 2000)

        # Check raw payload
        self.assertEqual(
            restored.payload,
            {"ip": "192.168.0.50", "video_port": 1000, "control_port": 2000}
        )

    def test_peek_type(self) -> None:
        pi = PeerInfo(ip="10.0.0.5", video_port=1111, control_port=2222)
        data = pi.to_bytes()
        self.assertEqual(Message.peek_type(data), "PeerInfo")

    def test_missing_required_field_raises_typeerror(self) -> None:
        pi = PeerInfo(ip="10.0.0.5", video_port=1111, control_port=2222)
        obj = msgpack.unpackb(pi.to_bytes())
        obj["p"].pop("ip")  # remove required arg
        broken = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(broken)

    def test_missing_top_level_p_raises_valueerror(self) -> None:
        pi = PeerInfo(ip="10.0.0.5", video_port=1111, control_port=2222)
        obj = msgpack.unpackb(pi.to_bytes())
        obj.pop("p")
        broken = msgpack.packb(obj)
        with self.assertRaises(ValueError):
            Message.from_bytes(broken)

    def test_extra_field_in_payload_raises_typeerror(self) -> None:
        pi = PeerInfo(ip="10.0.0.5", video_port=1111, control_port=2222)
        obj = msgpack.unpackb(pi.to_bytes())
        obj["p"]["unexpected"] = "nope"
        altered = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(altered)

    def test_unknown_message_type_raises(self) -> None:
        pi = PeerInfo(ip="10.0.0.5", video_port=1111, control_port=2222)
        obj = msgpack.unpackb(pi.to_bytes())
        obj["t"] = "NotARealType"
        bad = msgpack.packb(obj)
        with self.assertRaisesRegex(ValueError, r"Unknown message type: NotARealType"):
            Message.from_bytes(bad)

    def test_non_mapping_msgpack_raises_valueerror(self) -> None:
        non_mapping = msgpack.packb([1, 2, 3])  # top-level must be dict
        with self.assertRaises(ValueError):
            Message.from_bytes(non_mapping)

    def test_repr_smoke(self) -> None:
        pi = PeerInfo(ip="10.0.0.5", video_port=1111, control_port=2222)
        r = repr(pi)
        self.assertIn("PeerInfo", r)
        self.assertIn("payload=", r)
