import time
import socket
from src.rpi_4g_streamer import UDPTransmitter, Server
from src.rpi_4g_streamer import Heartbeat
from .config import HOST, PORT, SLEEP


def test_server():
    server = Server(PORT)
    server.start()
    server.stop()
    server.join()


def test_server_receive():
    sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_tx.settimeout(1)

    server = Server(PORT)
    server.start()

    tx = UDPTransmitter(sock_tx)
    tx.start()
    tx.start_task()

    tx.add_message(Heartbeat(), (HOST, PORT))

    time.sleep(SLEEP)

    server.stop()
    tx.stop()

    server.join()
    tx.join()

    sock_tx.close()
