import socket
import time
import unittest
from unittest.mock import Mock

from src.v3xctrl_control import MessageHandler, UDPTransmitter
from src.v3xctrl_control.Message import Heartbeat, Ack

from tests.v3xctrl_control.config import HOST, PORT, SLEEP


class TestMessageHandler(unittest.TestCase):
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
        self.handler = MessageHandler(self.sock_rx)
        self.handler.start()

        self.transmitter = UDPTransmitter(self.sock_tx)
        self.transmitter.start()
        self.transmitter.start_task()

    def tearDown(self):
        self.transmitter.stop()
        self.transmitter.join()

        self.handler.stop()
        self.handler.join()

        self.assertFalse(self.handler.running.is_set())

    def test_handler_lifecycle(self):
        # Already tested via setUp/tearDown, just assert lifecycle is correct
        self.assertTrue(self.handler.started.is_set())

    def test_handle_single_heartbeat(self):
        hb_mock = Mock()
        self.handler.add_handler(Heartbeat, hb_mock)

        self.transmitter.add_message(Heartbeat(), (HOST, PORT))
        time.sleep(SLEEP)

        hb_mock.assert_called_once()

    def test_handle_multiple_handlers_same_type(self):
        hb_mock_1 = Mock()
        hb_mock_2 = Mock()

        self.handler.add_handler(Heartbeat, hb_mock_1)
        self.handler.add_handler(Heartbeat, hb_mock_2)

        self.transmitter.add_message(Heartbeat(), (HOST, PORT))
        time.sleep(SLEEP)

        hb_mock_1.assert_called_once()
        hb_mock_2.assert_called_once()

    def test_handle_different_message_types(self):
        hb_mock = Mock()
        ack_mock = Mock()

        self.handler.add_handler(Heartbeat, hb_mock)
        self.handler.add_handler(Ack, ack_mock)

        self.transmitter.add_message(Heartbeat(), (HOST, PORT))
        self.transmitter.add_message(Ack(), (HOST, PORT))
        time.sleep(SLEEP)

        hb_mock.assert_called_once()
        ack_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
