import time

from src.rpi_4g_streamer import UDPTransmitter, UDPPacket, Server
from src.rpi_4g_streamer import Heartbeat


HOST = '127.0.0.1'
PORT = 6666


def test_server():
    server = Server(PORT)
    server.start()
    server.stop()
    server.join()


def test_server_receive():
    server = Server(PORT)
    server.start()

    tx = UDPTransmitter()
    tx.start()
    tx.start_task()

    heartbeat = Heartbeat()
    packet = UDPPacket(heartbeat.to_bytes(), HOST, PORT)
    tx.add(packet)

    time.sleep(3)

    server.stop()
    tx.stop()

    server.join()
    tx.join()
