import socket
import time
import unittest

from src.rpi_4g_streamer import UDPReceiver
from src.rpi_4g_streamer.Message import Message


class FakeMessage:
    def __init__(self, timestamp: int):
        self.timestamp = timestamp

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

        try:
            # Try to use IPv6 first
            self.sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            self.sock.bind(('::1', 0))
            self.host = '::1'
        except OSError:
            # Fallback to IPv4
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(('127.0.0.1', 0))
            self.host = '127.0.0.1'

        self.port = self.sock.getsockname()[1]

        self.receiver = UDPReceiver(self.sock, self.handler, timeout=0.2)
        self.receiver.start()

    def tearDown(self):
        self.receiver.stop()
        self.receiver.join()
        self.sock.close()

        # Restore original Message.from_bytes
        Message.from_bytes = self.original_from_bytes

    def send(self, data: bytes, host=None):
        if host is None:
            host = self.host
        self.sock.sendto(data, (host, self.port))

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

    def test_host_validation(self):
        self.receiver.validate_host(self.host)
        self.send(b"10")
        time.sleep(0.1)

        self.assertEqual(len(self.received), 1)

    def test_message_from_wrong_host_is_ignored(self):
        wrong_host = '1.2.3.4' if ':' not in self.host else '::2'
        self.receiver.validate_host(wrong_host)
        self.send(b"10")
        time.sleep(0.1)

        self.assertEqual(len(self.received), 0)

    def test_stop_cleanly(self):
        self.assertTrue(self.receiver.is_running())
        self.receiver.stop()
        self.receiver.join()
        self.assertFalse(self.receiver.is_alive())


if __name__ == '__main__':
    unittest.main()
