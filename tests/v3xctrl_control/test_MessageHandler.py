import socket
import time
import unittest
from unittest.mock import Mock, patch

from src.v3xctrl_control import MessageHandler, UDPTransmitter
from src.v3xctrl_control.message import Heartbeat, Ack, Message
from tests.v3xctrl_control.config import HOST, PORT, SLEEP


class DummyMessage(Message):
    def __init__(self) -> None:
        super().__init__({}, None)


class TestMessageHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cls.sock_tx.settimeout(1)

        cls.sock_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cls.sock_rx.bind((HOST, PORT))
        cls.sock_rx.settimeout(1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.sock_tx.close()
        cls.sock_rx.close()

    def setUp(self) -> None:
        self.handler = MessageHandler(self.sock_rx)
        self.handler.start()

        self.transmitter = UDPTransmitter(self.sock_tx)
        self.transmitter.start()
        self.transmitter.start_task()

    def tearDown(self) -> None:
        self.transmitter.stop()
        self.transmitter.join()

        self.handler.stop()
        self.handler.join()

        self.assertFalse(self.handler.running.is_set())

    def test_handler_lifecycle(self) -> None:
        self.assertTrue(self.handler.started.is_set())

    def test_handle_single_heartbeat(self) -> None:
        hb_mock = Mock()
        self.handler.add_handler(Heartbeat, hb_mock)

        self.transmitter.add_message(Heartbeat(), (HOST, PORT))
        time.sleep(SLEEP)

        hb_mock.assert_called_once()
        args, _ = hb_mock.call_args
        self.assertIsInstance(args[0], Heartbeat)

        # Only check IP, since UDP sender port is ephemeral
        self.assertEqual(args[1][0], HOST)
        self.assertIsInstance(args[1][1], int)

    def test_handle_multiple_handlers_same_type(self) -> None:
        hb_mock_1 = Mock()
        hb_mock_2 = Mock()

        self.handler.add_handler(Heartbeat, hb_mock_1)
        self.handler.add_handler(Heartbeat, hb_mock_2)

        self.transmitter.add_message(Heartbeat(), (HOST, PORT))
        time.sleep(SLEEP)

        hb_mock_1.assert_called_once()
        hb_mock_2.assert_called_once()

    def test_handle_different_message_types(self) -> None:
        hb_mock = Mock()
        ack_mock = Mock()

        self.handler.add_handler(Heartbeat, hb_mock)
        self.handler.add_handler(Ack, ack_mock)

        self.transmitter.add_message(Heartbeat(), (HOST, PORT))
        self.transmitter.add_message(Ack(), (HOST, PORT))
        time.sleep(SLEEP)

        hb_mock.assert_called_once()
        ack_mock.assert_called_once()

    def test_no_matching_handlers(self) -> None:
        ack_mock = Mock()
        self.handler.add_handler(Ack, ack_mock)
        self.transmitter.add_message(Heartbeat(), (HOST, PORT))
        time.sleep(SLEEP)
        ack_mock.assert_not_called()

    def test_generic_message_handler_called_for_subclass(self) -> None:
        """Handler registered for base Message should receive Heartbeat."""
        generic_mock = Mock()
        self.handler.add_handler(Message, generic_mock)

        self.transmitter.add_message(Heartbeat(), (HOST, PORT))
        time.sleep(SLEEP)

        generic_mock.assert_called_once()
        arg_msg, arg_addr = generic_mock.call_args[0]
        self.assertIsInstance(arg_msg, Heartbeat)
        self.assertEqual(arg_addr[0], HOST)

    def test_generic_and_specific_handlers_both_called_generic_first(self) -> None:
        """
        With current per-class bucket logic, if Message is registered before Heartbeat,
        generic handlers run before specific ones.
        """
        calls = []
        def generic(m: Message, _addr): calls.append(("generic", type(m).__name__))
        def specific(m: Heartbeat, _addr): calls.append(("specific", type(m).__name__))

        # Class insertion order: Message first, then Heartbeat
        self.handler.add_handler(Message, generic)
        self.handler.add_handler(Heartbeat, specific)

        self.transmitter.add_message(Heartbeat(), (HOST, PORT))
        time.sleep(SLEEP)

        self.assertEqual(calls, [("generic", "Heartbeat"), ("specific", "Heartbeat")])

    def test_generic_and_specific_handlers_both_called_specific_first(self) -> None:
        """
        If Heartbeat is registered before Message, class insertion order makes specific run first.
        """
        calls = []
        def generic(m: Message, _addr): calls.append(("generic", type(m).__name__))
        def specific(m: Heartbeat, _addr): calls.append(("specific", type(m).__name__))

        # Class insertion order: Heartbeat first, then Message
        self.handler.add_handler(Heartbeat, specific)
        self.handler.add_handler(Message, generic)

        self.transmitter.add_message(Heartbeat(), (HOST, PORT))
        time.sleep(SLEEP)

        self.assertEqual(calls, [("specific", "Heartbeat"), ("generic", "Heartbeat")])

    def test_generic_handler_only_no_specific_called(self) -> None:
        """Only generic handler present; it should still be called for Heartbeat."""
        generic_mock = Mock()
        specific_mock = Mock()

        self.handler.add_handler(Message, generic_mock)

        self.transmitter.add_message(Heartbeat(), (HOST, PORT))
        time.sleep(SLEEP)

        generic_mock.assert_called_once()
        specific_mock.assert_not_called()

    def test_valid_host_ip_calls_validate_host(self) -> None:
        with patch("src.v3xctrl_control.MessageHandler.UDPReceiver.validate_host") as mock_validate:
            mh = MessageHandler(self.sock_rx, valid_host_ip="127.0.0.1")
            mock_validate.assert_called_once_with("127.0.0.1")

    def test_handler_no_matching_type_direct_call(self) -> None:
        mh = MessageHandler(self.sock_rx)
        mh.handlers.clear()
        # Should simply do nothing without raising
        mh.handler(DummyMessage(), ("127.0.0.1", 5000))

    def test_stop_without_start(self) -> None:
        mh = MessageHandler(self.sock_rx)
        # started is never set; stop should be a no-op without errors
        mh.stop()

    def test_stop_clears_events(self) -> None:
        mh = MessageHandler(self.sock_rx)
        mh.started.set()
        mh.running.set()
        mh.rx = Mock()
        mh.stop()
        self.assertFalse(mh.started.is_set())
        self.assertFalse(mh.running.is_set())


if __name__ == "__main__":
    unittest.main()
