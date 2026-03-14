import unittest

import msgpack

from v3xctrl_control.message import ConnectionTestAck, Message


class TestConnectionTestAck(unittest.TestCase):
    def test_roundtrip_valid(self) -> None:
        msg = ConnectionTestAck(v=True)
        data = msg.to_bytes()
        restored = Message.from_bytes(data)
        self.assertIsInstance(restored, ConnectionTestAck)
        self.assertTrue(restored.valid)

    def test_roundtrip_invalid(self) -> None:
        msg = ConnectionTestAck(v=False)
        data = msg.to_bytes()
        restored = Message.from_bytes(data)
        self.assertIsInstance(restored, ConnectionTestAck)
        self.assertFalse(restored.valid)

    def test_missing_payload(self) -> None:
        msg = ConnectionTestAck(v=True)
        obj = msgpack.unpackb(msg.to_bytes())
        obj.pop("p")
        corrupted = msgpack.packb(obj)
        with self.assertRaises((TypeError, ValueError)):
            Message.from_bytes(corrupted)
