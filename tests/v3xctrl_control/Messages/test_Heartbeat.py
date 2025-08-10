import unittest
import msgpack
from v3xctrl_control.Message import Message, Heartbeat


class TestHeartbeat(unittest.TestCase):
    def test_roundtrip(self) -> None:
        hb = Heartbeat({})
        data = hb.to_bytes()
        restored = Message.from_bytes(data)
        self.assertIsInstance(restored, Heartbeat)
        self.assertEqual(restored.payload, {})

    def test_missing_payload(self) -> None:
        hb = Heartbeat({})
        obj = msgpack.unpackb(hb.to_bytes())
        obj.pop("p")  # Remove payload
        corrupted = msgpack.packb(obj)
        with self.assertRaises((TypeError, ValueError)):
            Message.from_bytes(corrupted)
