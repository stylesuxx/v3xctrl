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

    def test_client_lifecycle(self):
        client = Client(HOST, PORT)
        client.start()
        self.assertTrue(client.started.is_set())

        client.stop()
        client.join()
        self.assertFalse(client.running.is_set())
        self.assertFalse(client.started.is_set())

    def test_client_receive_message(self):
        client = Client(HOST, PORT)
        client.start()

        tx = UDPTransmitter(self.sock_tx)
        tx.start()
        tx.start_task()

        tx.add_message(Heartbeat(), (HOST, PORT))
        time.sleep(SLEEP)

        client.stop()
        tx.stop()

        client.join()
        tx.join()

        self.assertFalse(client.running.is_set())

    @patch("src.rpi_4g_streamer.Client.Base.send")
    def test_client_heartbeat_triggers_send(self, mock_send):
        client = Client(HOST, PORT)
        client.initialize()

        client.state = State.CONNECTED
        client.last_sent_timeout = 1
        client.last_sent_timestamp = time.time() - 2

        client.check_heartbeat()
        self.assertTrue(mock_send.called)
        msg, addr = mock_send.call_args[0]
        self.assertIsInstance(msg, Heartbeat)
        self.assertEqual(addr, (HOST, PORT))

        client.message_handler.stop()
        client.transmitter.stop()
        client.message_handler.join()
        client.transmitter.join()
        client.socket.close()

    @patch("src.rpi_4g_streamer.Client.Base.send")
    def test_client_no_heartbeat_if_recent(self, mock_send):
        client = Client(HOST, PORT)
        client.initialize()

        client.state = State.CONNECTED
        client.last_sent_timeout = 10
        client.last_sent_timestamp = time.time()

        client.check_heartbeat()
        mock_send.assert_not_called()

        client.message_handler.stop()
        client.transmitter.stop()
        client.message_handler.join()
        client.transmitter.join()
        client.socket.close()


if __name__ == "__main__":
    unittest.main()
