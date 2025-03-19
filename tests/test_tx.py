from src.rpi_4g_streamer import UDPTransmitter

PORT = 6666


def test_udp_transmission():
    transmitter = UDPTransmitter()
    transmitter.start()
    transmitter.stop()
    transmitter.join()

    assert not transmitter.running.is_set()
