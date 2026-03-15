import socket
import unittest

from src.v3xctrl_control import UDPPacket, UDPTransmitter


class FakeMessage:
    def __init__(self, value):
        self.value = value

    def to_bytes(self):
        return self.value.encode()


class TestUDPTransmitter(unittest.TestCase):
    def setUp(self):
        # Setup a UDP socket pair
        self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_sock.bind(("localhost", 0))
        self.host, self.port = self.recv_sock.getsockname()

        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.transmitter = UDPTransmitter(self.send_sock)
        self.transmitter.start()
        self.transmitter.start_task()

    def tearDown(self):
        self.transmitter.stop()
        self.send_sock.close()
        self.recv_sock.close()

    def test_packet_is_sent(self):
        packet = UDPPacket(b"test-123", self.host, self.port)
        self.transmitter.add(packet)

        self.recv_sock.settimeout(1)
        data, addr = self.recv_sock.recvfrom(1024)
        self.assertEqual(data, b"test-123")
        self.assertEqual(addr[0], "127.0.0.1")

    def test_add_message_sends_correct_data(self):
        msg = FakeMessage("hello-payload")
        self.transmitter.add_message(msg, (self.host, self.port))

        self.recv_sock.settimeout(1)
        data, _ = self.recv_sock.recvfrom(1024)
        self.assertEqual(data, b"hello-payload")

    def test_stop_cleans_up(self):
        self.transmitter.stop()
        self.assertFalse(self.transmitter.is_running())
        self.assertTrue(self.transmitter.process_stopped.is_set())
        self.assertIsNone(self.transmitter.task)

    def test_queue_multiple_packets(self):
        packets = [UDPPacket(f"msg-{i}".encode(), self.host, self.port) for i in range(5)]
        for p in packets:
            self.transmitter.add(p)

        received = []
        self.recv_sock.settimeout(1)
        for _ in range(5):
            data, _ = self.recv_sock.recvfrom(1024)
            received.append(data)

        self.assertEqual(len(received), 5)
        self.assertIn(b"msg-0", received)
        self.assertIn(b"msg-4", received)


class TestControlBuffer(unittest.TestCase):
    def setUp(self):
        self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_sock.bind(("localhost", 0))
        self.host, self.port = self.recv_sock.getsockname()

        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.transmitter = UDPTransmitter(self.send_sock)
        self.transmitter.start()
        self.transmitter.start_task()

    def tearDown(self):
        self.transmitter.stop()
        self.send_sock.close()
        self.recv_sock.close()

    def test_control_message_is_sent(self):
        msg = FakeMessage("control-1")
        self.transmitter.set_control_message(msg, (self.host, self.port))

        self.recv_sock.settimeout(1)
        data, _ = self.recv_sock.recvfrom(1024)
        self.assertEqual(data, b"control-1")

    def test_control_buffer_evicts_oldest(self):
        """With capacity=1, adding a second message evicts the first."""
        msg1 = FakeMessage("old")
        msg2 = FakeMessage("new")
        self.transmitter.set_control_message(msg1, (self.host, self.port))
        self.transmitter.set_control_message(msg2, (self.host, self.port))

        self.recv_sock.settimeout(1)
        data, _ = self.recv_sock.recvfrom(1024)
        self.assertEqual(data, b"new")

    def test_control_message_sent_before_regular(self):
        """Control messages should be processed before regular queue items."""
        # Pause the transmitter to queue up both types
        self.transmitter.stop()
        self.send_sock.close()

        # Fresh sockets and transmitter
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.transmitter = UDPTransmitter(self.send_sock)

        # Add regular message first, then control
        regular_msg = FakeMessage("regular")
        control_msg = FakeMessage("control")
        self.transmitter.add_message(regular_msg, (self.host, self.port))
        self.transmitter.set_control_message(control_msg, (self.host, self.port))

        # Now start - control should be sent first
        self.transmitter.start()
        self.transmitter.start_task()

        self.recv_sock.settimeout(1)
        first_data, _ = self.recv_sock.recvfrom(1024)
        second_data, _ = self.recv_sock.recvfrom(1024)

        self.assertEqual(first_data, b"control")
        self.assertEqual(second_data, b"regular")


class TestControlDropDetection(unittest.TestCase):
    def setUp(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.transmitter = UDPTransmitter(self.sock)

    def tearDown(self):
        self.sock.close()

    def test_no_drops_initially(self):
        self.assertFalse(self.transmitter.has_recent_control_drops())

    def test_drop_detected_after_eviction(self):
        msg1 = FakeMessage("a")
        msg2 = FakeMessage("b")
        addr = ("localhost", 9999)

        self.transmitter.set_control_message(msg1, addr)
        # This evicts msg1, triggering a drop
        self.transmitter.set_control_message(msg2, addr)

        self.assertTrue(self.transmitter.has_recent_control_drops())

    def test_drop_expires_after_window(self):
        msg1 = FakeMessage("a")
        msg2 = FakeMessage("b")
        addr = ("localhost", 9999)

        self.transmitter.set_control_message(msg1, addr)
        self.transmitter.set_control_message(msg2, addr)

        # Use a very short window to test expiration
        self.assertTrue(self.transmitter.has_recent_control_drops(window=10.0))
        self.assertFalse(self.transmitter.has_recent_control_drops(window=0.0))

    def test_no_drop_when_buffer_not_full(self):
        """With capacity > 1, adding one message should not trigger a drop."""
        self.sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        transmitter = UDPTransmitter(self.sock2, control_buffer_capacity=5)

        msg = FakeMessage("a")
        transmitter.set_control_message(msg, ("localhost", 9999))

        self.assertFalse(transmitter.has_recent_control_drops())
        self.sock2.close()


if __name__ == "__main__":
    unittest.main()
