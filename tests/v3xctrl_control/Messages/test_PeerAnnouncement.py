import unittest
import msgpack
from v3xctrl_control.Message import Message, PeerAnnouncement


class TestPeerAnnouncement(unittest.TestCase):
    def test_roundtrip(self) -> None:
        ts = 1_654_321.0
        pa = PeerAnnouncement(r="client", i="peer-123", p="control", timestamp=ts)
        data = pa.to_bytes()

        restored = Message.from_bytes(data)
        self.assertIsInstance(restored, PeerAnnouncement)
        self.assertEqual(restored.get_role(), "client")
        self.assertEqual(restored.get_id(), "peer-123")
        self.assertEqual(restored.get_port_type(), "control")
        self.assertEqual(restored.timestamp, ts)

        # payload stability
        self.assertEqual(restored.payload, {"r": "client", "i": "peer-123", "p": "control"})

    def test_peek_type(self) -> None:
        pa = PeerAnnouncement(r="viewer", i="abc", p="video")
        data = pa.to_bytes()
        self.assertEqual(Message.peek_type(data), "PeerAnnouncement")

    def test_missing_required_field_raises(self) -> None:
        pa = PeerAnnouncement(r="client", i="peer-123", p="control")
        obj = msgpack.unpackb(pa.to_bytes())
        # remove a required ctor arg -> constructor will raise TypeError
        obj["p"].pop("i")
        corrupted = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(corrupted)

    def test_extra_field_raises(self) -> None:
        pa = PeerAnnouncement(r="client", i="peer-123", p="control")
        obj = msgpack.unpackb(pa.to_bytes())
        # add an unexpected kwarg -> constructor will raise TypeError
        obj["p"]["extra"] = "nope"
        altered = msgpack.packb(obj)
        with self.assertRaises(TypeError):
            Message.from_bytes(altered)

    def test_unknown_message_type(self) -> None:
        pa = PeerAnnouncement(r="client", i="peer-123", p="control")
        obj = msgpack.unpackb(pa.to_bytes())
        obj["t"] = "NotARealType"
        bad = msgpack.packb(obj)
        with self.assertRaisesRegex(ValueError, r"Unknown message type: NotARealType"):
            Message.from_bytes(bad)

    def test_repr_smoke(self) -> None:
        pa = PeerAnnouncement(r="client", i="peer-123", p="control")
        s = repr(pa)
        self.assertIn("PeerAnnouncement", s)
        self.assertIn("payload=", s)
