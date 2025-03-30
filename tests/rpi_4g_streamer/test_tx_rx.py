import pytest
from unittest.mock import Mock
import socket
import time

from src.rpi_4g_streamer import UDPReceiver, UDPTransmitter, Heartbeat, UDPPacket
from tests.rpi_4g_streamer.config import HOST, PORT, SLEEP


@pytest.fixture(scope="session", autouse=True)
def setup_teardown():
    """Runs before all tests and cleans up after all tests."""

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


def test_udp_transmit_receive():
    global sock_tx, sock_rx

    handler = Mock()

    receiver = UDPReceiver(sock_rx, handler)
    receiver.start()

    transmitter = UDPTransmitter(sock_tx)
    transmitter.start()
    transmitter.start_task()

    transmitter.add_message(Heartbeat(), (HOST, PORT))

    time.sleep(SLEEP)

    transmitter.stop()
    receiver.stop()

    transmitter.join()
    receiver.join()

    assert not transmitter.running.is_set()
    assert not receiver.running.is_set()
    handler.assert_called_once()


def test_udp_ignore_non_message_data():
    global sock_tx, sock_rx

    handler = Mock()

    receiver = UDPReceiver(sock_rx, handler)
    receiver.start()

    transmitter = UDPTransmitter(sock_tx)
    transmitter.start()
    transmitter.start_task()

    packet = UDPPacket(b"", HOST, PORT)
    transmitter.add(packet)

    time.sleep(SLEEP)

    transmitter.stop()
    receiver.stop()

    transmitter.join()
    receiver.join()

    assert not transmitter.running.is_set()
    assert not receiver.running.is_set()
    handler.assert_not_called()


def test_udp_ignore_out_of_order():
    global sock_tx, sock_rx

    handler = Mock()

    receiver = UDPReceiver(sock_rx, handler)
    receiver.start()

    transmitter = UDPTransmitter(sock_tx)
    transmitter.start()
    transmitter.start_task()

    transmitter.add_message(Heartbeat(10), (HOST, PORT))
    transmitter.add_message(Heartbeat(5), (HOST, PORT))
    transmitter.add_message(Heartbeat(20), (HOST, PORT))

    time.sleep(SLEEP)

    transmitter.stop()
    receiver.stop()

    transmitter.join()
    receiver.join()

    assert not transmitter.running.is_set()
    assert not receiver.running.is_set()
    handler.call_count == 2
