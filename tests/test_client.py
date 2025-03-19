import time

from src.rpi_4g_streamer import UDPTransmitter, UDPPacket, Client
from src.rpi_4g_streamer import Heartbeat


HOST = '127.0.0.1'
PORT = 6666


def test_client():
    client = Client(HOST, PORT)
    client.start()
    client.stop()
    client.join()


def test_client_receive():
    client = Client(HOST, PORT)
    client.start()

    tx = UDPTransmitter()
    tx.start()
    tx.start_task()

    heartbeat = Heartbeat()
    packet = UDPPacket(heartbeat.to_bytes(), HOST, PORT)
    tx.add(packet)

    time.sleep(3)

    client.stop()
    tx.stop()

    client.join()
    tx.join()
