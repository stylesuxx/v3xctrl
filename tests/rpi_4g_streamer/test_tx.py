import socket
from src.rpi_4g_streamer import UDPTransmitter


def test_udp_transmission():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1)

    transmitter = UDPTransmitter(sock)
    transmitter.start()
    transmitter.start_task()
    transmitter.stop()
    transmitter.join()

    sock.close()

    assert not transmitter.running.is_set()
