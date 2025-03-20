import socket

from src.rpi_4g_streamer import UDPReceiver


def test_udp_receiver():
    def handler(message, addr):
        pass

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1)

    receiver = UDPReceiver(sock, handler)
    receiver.start()
    receiver.stop()
    receiver.join()

    sock.close()

    assert not receiver.running.is_set()
