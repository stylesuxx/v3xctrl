import socket
import time
import unittest
from unittest.mock import Mock

from src.rpi_4g_streamer import (
  UDPReceiver,
  UDPTransmitter,
  UDPPacket
)
from src.rpi_4g_streamer.Message import Heartbeat
from tests.rpi_4g_streamer.config import HOST, PORT, SLEEP


class TestUDPTransmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cls.sock_tx.settimeout(1)

        cls.sock_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cls.sock_rx.bind((HOST, PORT))
        cls.sock_rx.settimeout(1)

    @classmethod
    def tearDownClass(cls):
        cls.sock_tx.close()
        cls.sock_rx.close()

    def setUp(self):
        self.handler = Mock()

        self.receiver = UDPReceiver(self.sock_rx, self.handler)
        self.receiver.start()

        self.transmitter = UDPTransmitter(self.sock_tx)
        self.transmitter.start()
        self.transmitter.start_task()

    def tearDown(self):
        self.transmitter.stop()
        self.receiver.stop()

        self.transmitter.join()
        self.receiver.join()

        self.assertFalse(self.transmitter.is_running())
        self.assertFalse(self.receiver.is_running())

    def test_udp_transmit_receive(self):
        self.transmitter.add_message(Heartbeat(), (HOST, PORT))
        time.sleep(SLEEP)

        self.handler.assert_called_once()

    def test_udp_ignore_non_message_data(self):
        packet = UDPPacket(b"", HOST, PORT)
        self.transmitter.add(packet)
        time.sleep(SLEEP)

        self.handler.assert_not_called()

    def test_udp_ignore_out_of_order(self):
        # Should only handle the messages with timestamps 10 and 20
        self.transmitter.add_message(Heartbeat(10), (HOST, PORT))
        self.transmitter.add_message(Heartbeat(5), (HOST, PORT))  # should be ignored
        self.transmitter.add_message(Heartbeat(20), (HOST, PORT))
        time.sleep(SLEEP)

        self.assertEqual(self.handler.call_count, 2)


if __name__ == "__main__":
    unittest.main()
