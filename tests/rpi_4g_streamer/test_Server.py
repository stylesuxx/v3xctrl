import time
import unittest
from unittest.mock import patch, MagicMock

from src.rpi_4g_streamer import Server, State
from src.rpi_4g_streamer.Message import Syn, Heartbeat, Message

from tests.rpi_4g_streamer.config import HOST, PORT


class TestServer(unittest.TestCase):
    def setUp(self):
        self.base_send_patcher = patch("src.rpi_4g_streamer.Server.Base._send")
        self.mock_base_send = self.base_send_patcher.start()

        self.patcher_transmitter = patch("src.rpi_4g_streamer.Server.UDPTransmitter")
        self.patcher_handler = patch("src.rpi_4g_streamer.Server.MessageHandler")

        self.mock_transmitter_cls = self.patcher_transmitter.start()
        self.mock_handler_cls = self.patcher_handler.start()

        self.mock_transmitter = MagicMock()
        self.mock_handler = MagicMock()
        self.mock_transmitter_cls.return_value = self.mock_transmitter
        self.mock_handler_cls.return_value = self.mock_handler

        self.server = Server(port=PORT)
        self.server.get_last_address = MagicMock(return_value=(HOST, PORT))

    def tearDown(self):
        self.base_send_patcher.stop()
        self.patcher_transmitter.stop()
        self.patcher_handler.stop()
        if self.server.running.is_set() or self.server.started.is_set():
            self.server.running.set()
            self.server.stop()
        self.server.socket.close()

    def test_initial_state(self):
        self.assertEqual(self.server.state, State.WAITING)
        self.assertFalse(self.server.started.is_set())
        self.assertFalse(self.server.running.is_set())

    def test_syn_handler_changes_state_and_sends_ack(self):
        self.server.state = State.WAITING
        msg = Syn()
        addr = (HOST, PORT)

        self.server.syn_handler(msg, addr)

        self.mock_base_send.assert_called_once()
        self.assertEqual(self.server.state, State.CONNECTED)

    def test_syn_handler_does_not_change_state_if_not_waiting(self):
        self.server.state = State.CONNECTED
        msg = Syn()
        addr = (HOST, PORT)

        self.server.syn_handler(msg, addr)

        self.mock_base_send.assert_called_once()
        self.assertEqual(self.server.state, State.CONNECTED)

    def test_send_with_address(self):
        msg = Message({})
        self.server.send(msg)
        self.mock_base_send.assert_called_once_with(msg, (HOST, PORT))

    def test_send_without_address(self):
        self.server.get_last_address.return_value = None
        msg = Message({})
        self.server.send(msg)
        self.mock_base_send.assert_not_called()

    def test_heartbeat_triggers_send(self):
        self.server.last_sent_timestamp = time.time() - 11
        self.server.last_sent_timeout = 10
        self.server.state = State.CONNECTED

        self.server.heartbeat()
        self.mock_base_send.assert_called_once()
        args = self.mock_base_send.call_args[0]
        self.assertIsInstance(args[0], Heartbeat)

    def test_heartbeat_does_not_send_too_early(self):
        self.server.last_sent_timestamp = time.time()
        self.server.last_sent_timeout = 10

        self.server.heartbeat()
        self.mock_base_send.assert_not_called()

    def test_stop_properly_shuts_down(self):
        self.server.started.set()
        self.server.running.set()

        self.server.stop()

        self.mock_transmitter.stop.assert_called_once()
        self.mock_handler.stop.assert_called_once()
        self.mock_transmitter.join.assert_called_once()
        self.mock_handler.join.assert_called_once()
        self.assertFalse(self.server.running.is_set())


if __name__ == "__main__":
    unittest.main()
