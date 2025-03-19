from unittest.mock import Mock
import time

from src.rpi_4g_streamer import MessageHandler
from src.rpi_4g_streamer import UDPPacket, Heartbeat, Ack, UDPTransmitter


HOST = '127.0.0.1'
PORT = 6666


def test_message_handler():
    handler = MessageHandler(PORT)
    handler.start()
    handler.stop()
    handler.join()

    assert not handler.running.is_set()


def test_message_handler_handle_heartbeat():
    hh_handler = Mock()

    handler = MessageHandler(PORT)
    handler.start()

    handler.add_handler(Heartbeat, hh_handler)

    transmitter = UDPTransmitter()
    transmitter.start()
    transmitter.start_task()

    heartbeat = Heartbeat()
    packet = UDPPacket(heartbeat.to_bytes(), HOST, PORT)
    transmitter.add(packet)

    # Allow some time to finish processing
    time.sleep(1)

    transmitter.stop()
    transmitter.join()

    handler.stop()
    handler.join()

    assert not handler.running.is_set()
    hh_handler.assert_called_once()


def test_message_handler_multi_handler():
    hh_handler_1 = Mock()
    hh_handler_2 = Mock()

    handler = MessageHandler(PORT)
    handler.start()

    handler.add_handler(Heartbeat, hh_handler_1)
    handler.add_handler(Heartbeat, hh_handler_2)

    transmitter = UDPTransmitter()
    transmitter.start()
    transmitter.start_task()

    heartbeat = Heartbeat()
    packet = UDPPacket(heartbeat.to_bytes(), HOST, PORT)
    transmitter.add(packet)

    # Allow some time to finish processing
    time.sleep(1)

    transmitter.stop()
    transmitter.join()

    handler.stop()
    handler.join()

    assert not handler.running.is_set()
    hh_handler_1.assert_called_once()
    hh_handler_2.assert_called_once()


def test_message_handler_different_handler():
    handler_1 = Mock()
    handler_2 = Mock()

    handler = MessageHandler(PORT)
    handler.start()

    handler.add_handler(Heartbeat, handler_1)
    handler.add_handler(Ack, handler_2)

    transmitter = UDPTransmitter()
    transmitter.start()
    transmitter.start_task()

    heartbeat = Heartbeat()
    packet = UDPPacket(heartbeat.to_bytes(), HOST, PORT)
    transmitter.add(packet)

    ack = Ack()
    packet = UDPPacket(ack.to_bytes(), HOST, PORT)
    transmitter.add(packet)

    # Allow some time to finish processing
    time.sleep(1)

    transmitter.stop()
    transmitter.join()

    handler.stop()
    handler.join()

    assert not handler.running.is_set()
    handler_1.assert_called_once()
    handler_2.assert_called_once()
