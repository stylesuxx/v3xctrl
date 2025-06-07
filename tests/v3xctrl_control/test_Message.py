import unittest
import time
import msgpack

from src.v3xctrl_control.Message import (
    Message,
    Heartbeat,
    Syn,
    Ack,
    SynAck,
    Latency,
    Telemetry,
    Command,
    CommandAck,
    Control,
    PeerAnnouncement,
    PeerInfo,
)


class TestMessages(unittest.TestCase):
    def assert_message_roundtrip(self, msg: Message, expected_cls):
        data = msg.to_bytes()
        deserialized = Message.from_bytes(data)

        self.assertIsInstance(deserialized, expected_cls)
        self.assertEqual(msg.timestamp, deserialized.timestamp)
        self.assertEqual(msg.payload, deserialized.payload)

    def test_telemetry_roundtrip(self):
        msg = Telemetry({"k1": 1, "k2": 2})
        self.assert_message_roundtrip(msg, Telemetry)

    def test_control_roundtrip(self):
        msg = Control({"roll": 1.0, "pitch": 2.0})
        self.assert_message_roundtrip(msg, Control)

    def test_command_roundtrip(self):
        msg = Command("reboot", {"now": True})
        self.assert_message_roundtrip(msg, Command)

    def test_command_with_custom_id(self):
        msg = Command("shutdown", {}, "abc-123")
        data = msg.to_bytes()
        result = Message.from_bytes(data)
        self.assertEqual(result.get_command_id(), "abc-123")

    def test_command_ack_roundtrip(self):
        msg = CommandAck("cmd-001")
        self.assert_message_roundtrip(msg, CommandAck)

    def test_heartbeat_roundtrip(self):
        msg = Heartbeat()
        self.assert_message_roundtrip(msg, Heartbeat)

    def test_syn_roundtrip(self):
        msg = Syn()
        self.assert_message_roundtrip(msg, Syn)

    def test_ack_roundtrip(self):
        msg = Ack()
        self.assert_message_roundtrip(msg, Ack)

    def test_synack_roundtrip(self):
        msg = SynAck()
        self.assert_message_roundtrip(msg, SynAck)

    def test_latency_roundtrip(self):
        msg = Latency()
        self.assert_message_roundtrip(msg, Latency)

    def test_peer_announcement_roundtrip(self):
        msg = PeerAnnouncement("viewer", "id123", "video")
        self.assert_message_roundtrip(msg, PeerAnnouncement)

    def test_peer_info_roundtrip(self):
        msg = PeerInfo("10.0.0.1", 5004, 5005)
        self.assert_message_roundtrip(msg, PeerInfo)

    def test_timestamp_progression(self):
        msg1 = Heartbeat()
        time.sleep(0.01)
        msg2 = Heartbeat()
        self.assertGreater(msg2.timestamp, msg1.timestamp)

    def test_future_timestamp_allowed(self):
        future_ts = time.time() + 3600
        msg = Heartbeat(timestamp=future_ts)
        self.assertEqual(msg.timestamp, future_ts)

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

    def test_invalid_format_raises(self):
        with self.assertRaises(Exception):
            Message.from_bytes(b"not-a-valid-msgpack")

    def test_missing_fields_raises(self):
        bad_data = {
            "t": "Command",
            "p": {"c": "reboot"},  # missing 'p' in parameters
            "d": time.time()
        }
        packed = msgpack.packb(bad_data)
        with self.assertRaises(TypeError):
            Message.from_bytes(packed)


if __name__ == "__main__":
    unittest.main()
