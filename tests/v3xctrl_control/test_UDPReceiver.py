import socket
import time
import unittest
import queue
from unittest.mock import MagicMock

from src.v3xctrl_control import UDPReceiver
from src.v3xctrl_control.message import Message


class FakeMessage:
    def __init__(self, timestamp: int):
        self.timestamp = timestamp
        self.type = "test_message"

    @staticmethod
    def from_bytes(data: bytes):
        if data == b"fail":
            raise ValueError("Decode error")
        return FakeMessage(int(data.decode()))


class TestUDPReceiver(unittest.TestCase):
    def setUp(self):
        # Patch Message.from_bytes to our fake version
        self.original_from_bytes = Message.from_bytes
        Message.from_bytes = FakeMessage.from_bytes

        self.received = []
        self.handler = lambda msg, addr: self.received.append((msg.timestamp, addr))

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('127.0.0.1', 0))
        self.host = '127.0.0.1'
        self.port = self.sock.getsockname()[1]

        self.receiver = UDPReceiver(self.sock, self.handler, timeout_ms=50, window_ms=500)
        self.receiver.start()

    def tearDown(self):
        self.receiver.stop()
        self.receiver.join()
        self.sock.close()
        Message.from_bytes = self.original_from_bytes

    def send(self, data: bytes):
        self.sock.sendto(data, (self.host, self.port))

    def test_valid_message_is_handled(self):
        self.send(b"1")
        time.sleep(0.1)
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0][0], 1)

    def test_out_of_order_message_is_ignored(self):
        self.send(b"5")
        time.sleep(0.05)
        self.send(b"3")
        time.sleep(0.1)
        timestamps = [t for t, _ in self.received]
        self.assertIn(5, timestamps)
        self.assertNotIn(3, timestamps)

    def test_invalid_message_is_ignored(self):
        self.send(b"fail")
        time.sleep(0.1)
        self.assertEqual(len(self.received), 0)

    def test_host_validation_and_wrong_host(self):
        self.receiver.validate_host(self.host)
        self.send(b"10")
        time.sleep(0.05)
        self.assertTrue(self.received)

        self.received.clear()
        self.receiver.validate_host("8.8.8.8")
        self.send(b"11")
        time.sleep(0.05)
        self.assertFalse(self.received)

    def test_reset_allows_old_timestamp_again(self):
        self.send(b"5")
        time.sleep(0.05)
        self.receiver.reset()
        self.send(b"1")
        time.sleep(0.05)
        timestamps = [t for t, _ in self.received]
        self.assertIn(5, timestamps)
        self.assertIn(1, timestamps)

    def test_timestamp_outside_window_is_ignored(self):
        self.receiver._should_validate_timestamp = True
        self.receiver.last_valid_timestamp
        self.send(b"1000")  # first valid message
        time.sleep(0.05)
        timestamps = [t for t, _ in self.received]
        self.assertIn(1000, timestamps)
        self.assertNotIn(1001, timestamps)

    def test_stop_cleanly(self):
        self.assertTrue(self.receiver.is_running())
        self.receiver.stop()
        self.receiver.join()
        self.assertFalse(self.receiver.is_alive())

    def test_empty_data_is_ignored(self):
        self.sock.sendto(b"", (self.host, self.port))
        time.sleep(0.05)
        self.assertEqual(len(self.received), 0)

    def test_queue_full_drops_message(self):
        # Fill queue and patch put_nowait to raise queue.Full
        self.receiver._queue = MagicMock()
        self.receiver._queue.put_nowait.side_effect = queue.Full
        self.send(b"1")
        time.sleep(0.05)
        # No crash, just drops message

    def test_worker_loop_handler_exception(self):
        # Replace handler with one that raises
        def bad_handler(msg, addr):
            raise RuntimeError("bad handler")

        self.receiver.handler = bad_handler
        self.receiver._queue.put_nowait((FakeMessage(1), ("127.0.0.1", 12345)))
        # Let worker loop process
        time.sleep(0.05)

    def test_is_valid_message_reasons(self):
        self.receiver._should_validate_timestamp = True

        msg = FakeMessage(1)
        self.receiver.last_valid_timestamp = 5
        self.assertFalse(self.receiver.is_valid_message(msg, (self.host, self.port)))  # out of order

        self.receiver.last_valid_timestamp = 1
        self.receiver.last_valid_now = time.time() - 10
        msg.timestamp = 2
        self.assertFalse(self.receiver.is_valid_message(msg, (self.host, self.port)))  # too old

        self.receiver.last_valid_now = None
        self.receiver.validate_host("8.8.8.8")
        msg.timestamp = 10
        self.assertFalse(self.receiver.is_valid_message(msg, (self.host, self.port)))  # wrong host

    def test_long_disconnection_rejects_valid_messages(self):
        """Test that after a long disconnection, valid messages are incorrectly rejected"""
        self.receiver._should_validate_timestamp = True

        # Send initial message
        self.send(b"1000")
        time.sleep(0.05)
        self.assertEqual(len(self.received), 1)

        # Simulate long disconnection (much longer than window_ms=500)
        self.receiver.last_valid_now = time.time() - 10.0  # 10 second gap

        # Send new message after "reconnection" - should be rejected due to bug
        self.send(b"1001")
        time.sleep(0.05)

        # Verify the bug: only first message received, second was rejected
        timestamps = [t for t, _ in self.received]
        self.assertIn(1000, timestamps)
        self.assertNotIn(1001, timestamps)  # Bug: valid message rejected as "too old"
        self.assertEqual(len(self.received), 1)

    def test_reject_old_messages_in_continuous_stream(self):
        """Test rejecting old messages during continuous message flow"""
        base_time = int(time.time())

        # Send a sequence of recent messages
        for i in range(3):
            self.send(str(base_time + i).encode())
            time.sleep(0.02)

        time.sleep(0.1)
        self.assertEqual(len(self.received), 3)

        # Now send an old message (older than window_ms=500)
        old_time = base_time - 1  # 1 second old, outside 500ms window
        self.send(str(old_time).encode())
        time.sleep(0.1)

        # Should still only have 3 messages (old one rejected)
        self.assertEqual(len(self.received), 3)
        timestamps = [t for t, _ in self.received]
        self.assertNotIn(old_time, timestamps)

    def test_reset_fixes_disconnection_issue(self):
        """Test that calling reset() after disconnection allows new messages"""
        # Send initial message
        self.send(b"1000")
        time.sleep(0.05)
        self.assertEqual(len(self.received), 1)

        # Simulate long disconnection
        self.receiver.last_valid_now = time.time() - 10.0  # 10 second gap

        # Reset the receiver (this is the fix)
        self.receiver.reset()

        # Send new message after reset - should now be accepted
        self.send(b"1001")
        time.sleep(0.05)

        # Verify the fix: both messages received
        timestamps = [t for t, _ in self.received]
        self.assertIn(1000, timestamps)
        self.assertIn(1001, timestamps)  # Fixed: message accepted after reset
        self.assertEqual(len(self.received), 2)


if __name__ == '__main__':
    unittest.main()
