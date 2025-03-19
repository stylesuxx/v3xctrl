from src.rpi_4g_streamer import UDPReceiver

PORT = 6666


def test_udp_receiver():
    def handler(message, addr):
        pass

    receiver = UDPReceiver(PORT, handler)
    receiver.start()
    receiver.stop()
    receiver.join()

    assert not receiver.running.is_set()
