import socket
import time
import unittest
from unittest.mock import patch

from src.rpi_4g_streamer import Client, UDPTransmitter, State
from src.rpi_4g_streamer.Message import Heartbeat

from tests.rpi_4g_streamer.config import HOST, PORT, SLEEP


class TestClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cls.sock_tx.settimeout(1)

    @classmethod
    def tearDownClass(cls):
        cls.sock_tx.close()

    def setUp(self):
        # Setup fresh client for each test
        self.client = Client(HOST, PORT)

    def tearDown(self):
        # Clean up client after each test
        if self.client.running.is_set():
            self.client.stop()
            self.client.join()
        elif self.client.started.is_set():
            self.client.running.set()
            self.client.stop()
            self.client.join()

    def test_client_lifecycle(self):
        self.client.start()
        self.assertTrue(self.client.started.is_set())

        self.client.stop()
        self.client.join()
        self.assertFalse(self.client.running.is_set())
        self.assertFalse(self.client.started.is_set())

    def test_client_receive_message(self):
        self.client.start()

        tx = UDPTransmitter(self.sock_tx)
        tx.start()
        tx.start_task()

        tx.add_message(Heartbeat(), (HOST, PORT))
        time.sleep(SLEEP)

        tx.stop()
        tx.join()

        self.client.stop()
        self.client.join()

        self.assertFalse(self.client.running.is_set())

    @patch("src.rpi_4g_streamer.Client.Base._send")
    def test_client_heartbeat_triggers_send(self, mock_send):
        self.client.initialize()

        self.client.state = State.CONNECTED
        self.client.last_sent_timeout = 1
        self.client.last_sent_timestamp = time.time() - 2

        self.client.heartbeat()
        self.assertTrue(mock_send.called)
        msg, addr = mock_send.call_args[0]
        self.assertIsInstance(msg, Heartbeat)
        self.assertEqual(addr, (HOST, PORT))

        self.client.message_handler.stop()
        self.client.transmitter.stop()
        self.client.message_handler.join()
        self.client.transmitter.join()
        self.client.socket.close()

    @patch("src.rpi_4g_streamer.Client.Base._send")
    def test_client_no_heartbeat_if_recent(self, mock_send):
        self.client.initialize()

        self.client.state = State.CONNECTED
        self.client.last_sent_timeout = 10
        self.client.last_sent_timestamp = time.time()

        self.client.heartbeat()
        mock_send.assert_not_called()

        self.client.message_handler.stop()
        self.client.transmitter.stop()
        self.client.message_handler.join()
        self.client.transmitter.join()
        self.client.socket.close()


if __name__ == "__main__":
    unittest.main()
