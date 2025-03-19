import unittest
from unittest.mock import Mock
import time

from src.rpi_4g_streamer import UDPReceiver, UDPTransmitter, Heartbeat, UDPPacket

PORT = 6666
HOST = '127.0.0.1'


def test_udp_transmit_receive():
    handler = Mock()

    receiver = UDPReceiver(PORT, handler)
    receiver.start()

    transmitter = UDPTransmitter()
    transmitter.start()
    transmitter.start_task()

    heartbeat = Heartbeat()
    packet = UDPPacket(heartbeat.to_bytes(), HOST, PORT)
    transmitter.add(packet)

    time.sleep(1)

    transmitter.stop()
    receiver.stop()

    transmitter.join()
    receiver.join()

    assert not transmitter.running.is_set()
    assert not receiver.running.is_set()
    handler.assert_called_once()


def test_udp_ignore_non_message_data():
    handler = Mock()

    receiver = UDPReceiver(PORT, handler)
    receiver.start()

    transmitter = UDPTransmitter()
    transmitter.start()
    transmitter.start_task()

    packet = UDPPacket(b"", HOST, PORT)
    transmitter.add(packet)

    time.sleep(1)

    transmitter.stop()
    receiver.stop()

    transmitter.join()
    receiver.join()

    assert not transmitter.running.is_set()
    assert not receiver.running.is_set()
    handler.assert_not_called()


def test_udp_ignore_out_of_order():
    handler = Mock()

    receiver = UDPReceiver(PORT, handler)
    receiver.start()

    transmitter = UDPTransmitter()
    transmitter.start()
    transmitter.start_task()

    heartbeat = Heartbeat(10)
    packet = UDPPacket(heartbeat.to_bytes(), HOST, PORT)
    transmitter.add(packet)

    heartbeat = Heartbeat(5)
    packet = UDPPacket(heartbeat.to_bytes(), HOST, PORT)
    transmitter.add(packet)

    heartbeat = Heartbeat(20)
    packet = UDPPacket(heartbeat.to_bytes(), HOST, PORT)
    transmitter.add(packet)

    time.sleep(1)

    transmitter.stop()
    receiver.stop()

    transmitter.join()
    receiver.join()

    assert not transmitter.running.is_set()
    assert not receiver.running.is_set()
    handler.call_count == 2
