import time
import socket

from src.rpi_4g_streamer import UDPTransmitter, Client
from src.rpi_4g_streamer import Heartbeat
from tests.rpi_4g_streamer.config import HOST, PORT, SLEEP


def test_client():
    client = Client(HOST, PORT)
    client.start()
    client.stop()
    client.join()


def test_client_receive():
    sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_tx.settimeout(1)

    client = Client(HOST, PORT)
    client.start()

    tx = UDPTransmitter(sock_tx)
    tx.start()
    tx.start_task()

    tx.add_message(Heartbeat(), (HOST, PORT))

    time.sleep(SLEEP)

    client.stop()
    tx.stop()

    client.join()
    tx.join()
