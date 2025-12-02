import time
import unittest
from unittest.mock import Mock

from src.v3xctrl_control.Base import Base
from src.v3xctrl_control.message import Heartbeat, Control, Message
from src.v3xctrl_control.State import State
from src.v3xctrl_helper import MessageFromAddress


class DummyBase(Base):
    """Concrete implementation for testing Base."""
    def __init__(self) -> None:
        super().__init__()
        self.sent_messages = []

    def send(self, message: Message) -> None:
        self.sent_messages.append(message)


class TestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.base = DummyBase()

    def test_init_defaults(self) -> None:
        self.assertEqual(self.base.state_handlers, {})
        self.assertEqual(self.base.subscriptions, {})
        self.assertEqual(self.base.message_history, [])
        self.assertEqual(self.base.message_history_length, 50)
        self.assertFalse(self.base.running.is_set())
        self.assertFalse(self.base.started.is_set())
        self.assertEqual(self.base.state, State.WAITING)
        self.assertIsNone(self.base.socket)
        self.assertIsNone(self.base.transmitter)
        self.assertIsNone(self.base.message_handler)
        self.assertEqual(self.base.last_message_timestamp, 0)
        self.assertEqual(self.base.no_message_timeout, 5)
        self.assertEqual(self.base.last_sent_timestamp, 0)
        self.assertEqual(self.base.last_sent_timeout, 1)

    def test_subscribe_and_all_handler_match(self) -> None:
        handler_mock = Mock()
        self.base.subscribe(Heartbeat, handler_mock)

        hb = Heartbeat()
        addr = ("127.0.0.1", 5000)
        self.base.all_handler(hb, addr)

        handler_mock.assert_called_once_with(hb, addr)
        self.assertEqual(self.base.message_history[-1], MessageFromAddress(hb, addr))
        self.assertIsNotNone(self.base.last_message_timestamp)

    def test_subscribe_generic_message_handler_match(self) -> None:
        handler_generic = Mock()
        self.base.subscribe(Message, handler_generic)

        hb = Heartbeat()
        addr = ("127.0.0.1", 5000)
        self.base.all_handler(hb, addr)

        handler_generic.assert_called_once_with(hb, addr)
        self.assertEqual(self.base.message_history[-1], MessageFromAddress(hb, addr))

    def test_both_generic_and_specific_handlers_fire_in_registration_order(self) -> None:
        calls = []

        def generic_handler(m: Message, a):
            calls.append(("generic", type(m).__name__))

        def specific_handler(m: Heartbeat, a):
            calls.append(("specific", type(m).__name__))

        self.base.subscribe(Message, generic_handler)
        self.base.subscribe(Heartbeat, specific_handler)

        hb = Heartbeat()
        self.base.all_handler(hb, ("127.0.0.1", 5000))

        self.assertEqual(
            calls,
            [("generic", "Heartbeat"), ("specific", "Heartbeat")]
        )

    def test_all_handler_no_match(self) -> None:
        handler_mock = Mock()
        self.base.subscribe(Control, handler_mock)
        self.base.all_handler(Heartbeat(), ("127.0.0.1", 5000))
        handler_mock.assert_not_called()

    def test_on_and_handle_state_change_match(self) -> None:
        handler_mock = Mock()
        self.base.on(State.DISCONNECTED, handler_mock)
        self.base.handle_state_change(State.DISCONNECTED)
        self.assertEqual(self.base.state, State.DISCONNECTED)
        handler_mock.assert_called_once()

    def test_handle_state_change_no_match(self) -> None:
        handler_mock = Mock()
        self.base.on(State.CONNECTED, handler_mock)
        self.base.handle_state_change(State.DISCONNECTED)
        handler_mock.assert_not_called()

    def test_heartbeat_sends_when_timeout_exceeded(self) -> None:
        self.base.last_sent_timestamp = time.time() - 10
        self.base.last_sent_timeout = 1
        self.base.heartbeat()
        self.assertTrue(any(isinstance(m, Heartbeat) for m in self.base.sent_messages))

    def test_heartbeat_does_not_send_when_recent(self) -> None:
        self.base.last_sent_timestamp = time.time()
        self.base.heartbeat()
        self.assertFalse(self.base.sent_messages)

    def test_send_abstract_coverage(self) -> None:
        result = super(DummyBase, self.base).send(Heartbeat())
        self.assertIsNone(result)

    def test__send_with_transmitter(self) -> None:
        mock_transmitter = Mock()
        self.base.transmitter = mock_transmitter

        hb = Heartbeat()
        addr = ("127.0.0.1", 5000)
        self.base._send(hb, addr)

        mock_transmitter.add_message.assert_called_once_with(hb, addr)
        self.assertAlmostEqual(self.base.last_sent_timestamp, time.time(), delta=0.1)

    def test__send_without_transmitter(self) -> None:
        hb = Heartbeat()
        ts_before = self.base.last_sent_timestamp
        self.base._send(hb, ("127.0.0.1", 5000))
        self.assertEqual(self.base.last_sent_timestamp, ts_before)

    def test_get_last_address_empty_and_nonempty(self) -> None:
        self.assertIsNone(self.base.get_last_address())
        addr = ("127.0.0.1", 5000)
        self.base.message_history.append(MessageFromAddress(Heartbeat(), addr))
        self.assertEqual(self.base.get_last_address(), addr)

    def test_check_timeout_triggers_state_change(self) -> None:
        self.base.state = State.CONNECTED
        self.base.last_message_timestamp = time.monotonic() - 10
        self.base.no_message_timeout = 1

        mock_handler = Mock()
        self.base.on(State.DISCONNECTED, mock_handler)

        self.base.check_timeout()

        self.assertEqual(self.base.state, State.DISCONNECTED)
        mock_handler.assert_called_once()

    def test_check_timeout_does_nothing_if_disconnected(self) -> None:
        self.base.state = State.DISCONNECTED
        self.base.last_message_timestamp = 0
        self.base.check_timeout()
        self.assertEqual(self.base.state, State.DISCONNECTED)

    def test_message_history_trimming(self) -> None:
        self.base.message_history_length = 3
        addr = ("127.0.0.1", 5000)

        for _ in range(5):
            self.base.all_handler(Heartbeat(), addr)

        self.assertEqual(len(self.base.message_history), 3)


if __name__ == "__main__":
    unittest.main()
