import unittest
import time

from src.v3xctrl_control.Message import (
    Message,
    Heartbeat,
    Syn,
    Ack,
    Telemetry,
    Command,
    Control
)


class TestMessages(unittest.TestCase):
    def assert_message_roundtrip(self, msg: Message, expected_cls):
        data = msg.to_bytes()
        deserialized = Message.from_bytes(data)

        self.assertIsInstance(deserialized, expected_cls)
        self.assertEqual(msg.timestamp, deserialized.timestamp)
        self.assertEqual(msg.payload, deserialized.payload)

    def test_telemetry_roundtrip(self):
        payload = {"k1": 1, "k2": 2}
        msg = Telemetry(payload)
        self.assert_message_roundtrip(msg, Telemetry)

    def test_command_roundtrip(self):
        msg = Command("reboot", {})
        self.assert_message_roundtrip(msg, Command)

    def test_control_roundtrip(self):
        payload = {"roll": 1.0, "pitch": 2.0}
        msg = Control(payload)
        self.assert_message_roundtrip(msg, Control)

    def test_heartbeat_roundtrip(self):
        msg = Heartbeat()
        self.assert_message_roundtrip(msg, Heartbeat)

    def test_syn_roundtrip(self):
        msg = Syn()
        self.assert_message_roundtrip(msg, Syn)

    def test_ack_roundtrip(self):
        msg = Ack()
        self.assert_message_roundtrip(msg, Ack)

    def test_new_timestamp_is_later(self):
        msg = Heartbeat()
        time.sleep(0.01)
        msg2 = Heartbeat()
        self.assertGreater(msg2.timestamp, msg.timestamp)

    def test_unknown_type_raises(self):
        # simulate invalid message type
        bad_data = {
            "t": "NonexistentType",
            "p": {},
            "d": time.time()
        }
        import msgpack
        packed = msgpack.packb(bad_data)

        with self.assertRaises(ValueError) as ctx:
            Message.from_bytes(packed)
        self.assertIn("Unknown message type", str(ctx.exception))

    def test_invalid_format_raises(self):
        with self.assertRaises(Exception):
            Message.from_bytes(b"not-a-valid-msgpack")


if __name__ == "__main__":
    unittest.main()
