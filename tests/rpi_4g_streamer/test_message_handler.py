from unittest.mock import Mock
import time
import socket
import pytest

from src.rpi_4g_streamer import MessageHandler
from src.rpi_4g_streamer import Heartbeat, Ack, UDPTransmitter
from tests.rpi_4g_streamer.config import HOST, PORT, SLEEP


@pytest.fixture(scope="function", autouse=True)
def setup_teardown():
    global sock_tx, sock_rx
    sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_tx.settimeout(1)

    sock_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_rx.bind((HOST, PORT))
    sock_rx.settimeout(1)

    yield  # Run tests

    # Post-test teardown: Close sockets
    sock_tx.close()
    sock_rx.close()


def test_message_handler():
    global sock_tx, sock_rx

    handler = MessageHandler(sock_rx)
    handler.start()
    handler.stop()
    handler.join()

    assert not handler.running.is_set()


def test_message_handler_handle_heartbeat():
    global sock_tx, sock_rx

    hh_handler = Mock()

    handler = MessageHandler(sock_rx)
    handler.start()

    handler.add_handler(Heartbeat, hh_handler)

    transmitter = UDPTransmitter(sock_tx)
    transmitter.start()
    transmitter.start_task()

    transmitter.add_message(Heartbeat(), (HOST, PORT))

    # Allow some time to finish processing
    time.sleep(SLEEP)

    transmitter.stop()
    transmitter.join()

    handler.stop()
    handler.join()

    assert not handler.running.is_set()
    hh_handler.assert_called_once()


def test_message_handler_multi_handler():
    global sock_tx, sock_rx

    hh_handler_1 = Mock()
    hh_handler_2 = Mock()

    handler = MessageHandler(sock_rx)
    handler.start()

    handler.add_handler(Heartbeat, hh_handler_1)
    handler.add_handler(Heartbeat, hh_handler_2)

    transmitter = UDPTransmitter(sock_tx)
    transmitter.start()
    transmitter.start_task()

    transmitter.add_message(Heartbeat(), (HOST, PORT))

    # Allow some time to finish processing
    time.sleep(SLEEP)

    transmitter.stop()
    transmitter.join()

    handler.stop()
    handler.join()

    assert not handler.running.is_set()
    hh_handler_1.assert_called_once()
    hh_handler_2.assert_called_once()


def test_message_handler_different_handler():
    global sock_tx, sock_rx

    handler_1 = Mock()
    handler_2 = Mock()

    handler = MessageHandler(sock_rx)
    handler.start()

    handler.add_handler(Heartbeat, handler_1)
    handler.add_handler(Ack, handler_2)

    transmitter = UDPTransmitter(sock_tx)
    transmitter.start()
    transmitter.start_task()

    transmitter.add_message(Heartbeat(), (HOST, PORT))
    transmitter.add_message(Ack(), (HOST, PORT))

    # Allow some time to finish processing
    time.sleep(SLEEP)

    transmitter.stop()
    transmitter.join()

    handler.stop()
    handler.join()

    assert not handler.running.is_set()
    handler_1.assert_called_once()
    handler_2.assert_called_once()
