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
    Error,
)


class TestMessages(unittest.TestCase):
    def assert_message_roundtrip(self, msg: Message, expected_cls):
        """Helper to ensure serialization -> deserialization is lossless."""
        data = msg.to_bytes()
        deserialized = Message.from_bytes(data)

        self.assertIsInstance(deserialized, expected_cls)
        self.assertAlmostEqual(msg.timestamp, deserialized.timestamp, places=5)
        self.assertEqual(msg.payload, deserialized.payload)

    def test_telemetry_roundtrip(self):
        msg = Telemetry({"k1": 1, "k2": 2})
        self.assertEqual(msg.get_values(), {"k1": 1, "k2": 2})
        self.assert_message_roundtrip(msg, Telemetry)

    def test_control_roundtrip(self):
        msg = Control({"roll": 1.0, "pitch": 2.0})
        self.assertEqual(msg.get_values(), {"roll": 1.0, "pitch": 2.0})
        self.assert_message_roundtrip(msg, Control)

    def test_command_roundtrip_and_fields(self):
        msg = Command("reboot", {"now": True})
        self.assertEqual(msg.get_command(), "reboot")
        self.assertEqual(msg.get_parameters(), {"now": True})
        self.assertTrue(msg.get_command_id())
        self.assert_message_roundtrip(msg, Command)

    def test_command_id_auto_generated_format(self):
        msg = Command("test")
        cid = msg.get_command_id()
        self.assertRegex(cid, r"\d+-\d+")

    def test_command_with_custom_id(self):
        msg = Command("shutdown", {}, "abc-123")
        self.assertEqual(msg.get_command_id(), "abc-123")
        self.assert_message_roundtrip(msg, Command)

    def test_command_ack_roundtrip(self):
        msg = CommandAck("cmd-001")
        self.assertEqual(msg.get_command_id(), "cmd-001")
        self.assert_message_roundtrip(msg, CommandAck)

    def test_heartbeat_roundtrip(self):
        msg = Heartbeat()
        self.assert_message_roundtrip(msg, Heartbeat)

    def test_syn_roundtrip_and_version(self):
        msg = Syn()
        self.assertEqual(msg.get_version(), 1)
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

    def test_error_roundtrip(self):
        msg = Error(404)
        self.assertEqual(msg.get_error(), 404)
        self.assert_message_roundtrip(msg, Error)

    def test_peer_announcement_roundtrip_and_fields(self):
        msg = PeerAnnouncement("viewer", "id123", "video")
        self.assertEqual(msg.get_role(), "viewer")
        self.assertEqual(msg.get_id(), "id123")
        self.assertEqual(msg.get_port_type(), "video")
        self.assert_message_roundtrip(msg, PeerAnnouncement)

    def test_peer_info_roundtrip_and_fields(self):
        msg = PeerInfo("10.0.0.1", 5004, 5005)
        self.assertEqual(msg.get_ip(), "10.0.0.1")
        self.assertEqual(msg.get_video_port(), 5004)
        self.assertEqual(msg.get_control_port(), 5005)
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

    def test_partial_payload_handling(self):
        msg = Command("nop")
        data = msg.to_bytes()
        obj = msgpack.unpackb(data)
        del obj["p"]["p"]  # remove parameters
        repacked = msgpack.packb(obj)

        deserialized = Message.from_bytes(repacked)
        self.assertIsInstance(deserialized, Command)
        self.assertEqual(deserialized.get_command(), "nop")
        self.assertEqual(deserialized.get_parameters(), {})  # default value
        self.assertTrue(deserialized.get_command_id())  # default value

    def test_peek_type_valid(self):
        msg = Command("test", {"k": "v"})
        data = msg.to_bytes()
        self.assertEqual(Message.peek_type(data), "Command")

    def test_peek_type_invalid_msgpack(self):
        data = b"not-a-valid-msgpack"
        self.assertEqual(Message.peek_type(data), "Unknown")

    def test_peek_type_missing_type(self):
        data = msgpack.packb({"p": {}, "d": time.time()})
        self.assertEqual(Message.peek_type(data), "Unknown")


if __name__ == "__main__":
    unittest.main()
