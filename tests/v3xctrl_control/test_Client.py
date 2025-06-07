import socket
import time
import unittest
from unittest.mock import patch, MagicMock

from src.v3xctrl_control import Client, UDPTransmitter, State
from src.v3xctrl_control.Message import Heartbeat, Command, CommandAck

from tests.v3xctrl_control.config import HOST, PORT, SLEEP


class TestClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cls.sock_tx.settimeout(1)

    @classmethod
    def tearDownClass(cls):
        cls.sock_tx.close()

    def setUp(self):
        self.client = Client(HOST, PORT)

    def tearDown(self):
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

    @patch("src.v3xctrl_control.Client.Base._send")
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

    @patch("src.v3xctrl_control.Client.Base._send")
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

    @patch("src.v3xctrl_control.Client.Base._send")
    def test_client_command_handler_sends_ack(self, mock_send):
        self.client.initialize()

        # Simulate receiving a Command
        cmd = Command("ping", {})
        self.client.command_handler(cmd, (HOST, PORT))

        mock_send.assert_called_once()
        msg, addr = mock_send.call_args[0]
        self.assertIsInstance(msg, CommandAck)
        self.assertEqual(msg.get_command_id(), cmd.get_command_id())
        self.assertEqual(addr, (HOST, PORT))

        self.client.message_handler.stop()
        self.client.transmitter.stop()
        self.client.message_handler.join()
        self.client.transmitter.join()
        self.client.socket.close()


if __name__ == "__main__":
    unittest.main()
