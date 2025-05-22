import socket
import unittest

from src.v3xctrl_control import UDPTransmitter, UDPPacket


class FakeMessage:
    def __init__(self, value):
        self.value = value

    def to_bytes(self):
        return self.value.encode()


class TestUDPTransmitter(unittest.TestCase):
    def setUp(self):
        # Setup a UDP socket pair
        self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_sock.bind(('localhost', 0))
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


if __name__ == "__main__":
    unittest.main()
