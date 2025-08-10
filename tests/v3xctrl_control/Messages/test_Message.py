import unittest
import time
import msgpack

from src.v3xctrl_control.message import Message


class TestMessages(unittest.TestCase):
    def assert_message_roundtrip(self, msg: Message, expected_cls):
        """Helper to ensure serialization -> deserialization is lossless."""
        data = msg.to_bytes()
        deserialized = Message.from_bytes(data)

        self.assertIsInstance(deserialized, expected_cls)
        self.assertAlmostEqual(msg.timestamp, deserialized.timestamp, places=5)
        self.assertEqual(msg.payload, deserialized.payload)

    def test_unknown_type_raises(self):
        bad_data = {
            "t": "NonexistentType",
            "p": {},
            "d": time.time()
        }
        packed = msgpack.packb(bad_data)
        with self.assertRaises(ValueError) as ctx:
            Message.from_bytes(packed)
        self.assertIn("Unknown message type", str(ctx.exception))

    def test_invalid_msgpack_raises(self):
        # ExtraData triggers
        broken = msgpack.packb({"t": "Command", "p": {}, "d": time.time()}) + b"junk"
        with self.assertRaises(ValueError) as ctx:
            Message.from_bytes(broken)
        self.assertIn("Malformed", str(ctx.exception))

        # Completely invalid
        with self.assertRaises(ValueError):
            Message.from_bytes(b"not-a-valid-msgpack")

    def test_missing_keys_raises(self):
        broken = msgpack.packb({"t": "Command", "p": {}})
        with self.assertRaises(ValueError):
            Message.from_bytes(broken)

    def test_peek_type_invalid_msgpack(self):
        data = b"not-a-valid-msgpack"
        self.assertEqual(Message.peek_type(data), "Unknown")

    def test_peek_type_missing_type(self):
        data = msgpack.packb({"p": {}, "d": time.time()})
        self.assertEqual(Message.peek_type(data), "Unknown")


if __name__ == "__main__":
    unittest.main()
