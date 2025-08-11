# tests/v3xctrl_control/test_Client.py
import socket
import time
import unittest
from unittest.mock import patch, MagicMock

from src.v3xctrl_control import Client, UDPTransmitter, State
from src.v3xctrl_control.message import Heartbeat, Command, CommandAck, Syn, Ack, Message
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
        # Only join if thread was actually started
        if self.client.running.is_set():
            self.client.stop()
            if self.client.is_alive():
                self.client.join()
        elif self.client.started.is_set():
            self.client.running.set()
            self.client.stop()
            if self.client.is_alive():
                self.client.join()

    def test_client_lifecycle(self):
        self.client.start()
        self.assertTrue(self.client.running.is_set())

        self.client.stop()
        if self.client.is_alive():
            self.client.join()
        self.assertFalse(self.client.running.is_set())

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
        if self.client.is_alive():
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

    @patch("src.v3xctrl_control.Client.Base._send")
    def test_syn_handler_sends_ack(self, mock_send):
        self.client.syn_handler(Message({}), (HOST, PORT))
        mock_send.assert_called_once()
        self.assertIsInstance(mock_send.call_args[0][0], Ack)

    def test_ack_handler_sets_connected(self):
        self.client.state = State.WAITING
        self.client.ack_handler(Message({}), (HOST, PORT))
        self.assertEqual(self.client.state, State.CONNECTED)

    @patch.object(Client, "initialize")
    @patch.object(Client, "handle_state_change")
    def test_reinitialize_from_running(self, mock_handle, mock_init):
        self.client.running.set()
        self.client.message_handler = MagicMock()
        self.client.transmitter = MagicMock()
        self.client.socket = MagicMock()
        self.client.re_initialize()
        mock_init.assert_called_once()

    @patch.object(Client, "send")
    def test_run_branches(self, mock_send):
        # DISCONNECTED branch
        self.client.state = State.DISCONNECTED
        with patch.object(self.client, "re_initialize") as mock_reinit, \
             patch.object(self.client, "handle_state_change") as mock_handle, \
             patch("time.sleep", return_value=None):
            self.client.running.set()
            mock_reinit.side_effect = lambda: self.client.running.clear()
            self.client.run()
            mock_reinit.assert_called_once()
            mock_handle.assert_called_once_with(State.WAITING)

        # WAITING branch
        self.client.state = State.WAITING
        with patch("time.sleep", return_value=None):
            self.client.running.set()
            mock_send.side_effect = lambda msg: self.client.running.clear()
            self.client.run()
            # Only check type, not exact timestamp
            self.assertTrue(any(isinstance(call_args[0][0], Syn) for call_args in mock_send.call_args_list))

        # CONNECTED branch
        self.client.state = State.CONNECTED
        with patch.object(self.client, "heartbeat") as mock_hb, \
             patch.object(self.client, "check_timeout") as mock_ct, \
             patch("time.sleep", return_value=None):
            self.client.running.set()
            mock_hb.side_effect = lambda: self.client.running.clear()
            self.client.run()
            mock_hb.assert_called_once()
            mock_ct.assert_called_once()

    def test_stop_without_start(self):
        self.client.stop()  # started is not set, should do nothing
