import unittest

import msgpack

from v3xctrl_control.message import ConnectionTest, Message


class TestConnectionTest(unittest.TestCase):
    def test_roundtrip(self) -> None:
        msg = ConnectionTest(i="test_session", s=False)
        data = msg.to_bytes()
        restored = Message.from_bytes(data)
        self.assertIsInstance(restored, ConnectionTest)
        self.assertEqual(restored.id, "test_session")
        self.assertFalse(restored.spectator)

    def test_roundtrip_spectator(self) -> None:
        msg = ConnectionTest(i="spectator_id", s=True)
        data = msg.to_bytes()
        restored = Message.from_bytes(data)
        self.assertIsInstance(restored, ConnectionTest)
        self.assertEqual(restored.id, "spectator_id")
        self.assertTrue(restored.spectator)

    def test_missing_payload(self) -> None:
        msg = ConnectionTest(i="test", s=False)
        obj = msgpack.unpackb(msg.to_bytes())
        obj.pop("p")
        corrupted = msgpack.packb(obj)
        with self.assertRaises((TypeError, ValueError)):
            Message.from_bytes(corrupted)
