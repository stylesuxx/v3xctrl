import logging
import signal
import sys

from v3xctrl_udp_relay.UDPRelayServer import UDPRelayServer

logging.basicConfig(level=logging.DEBUG)
server = UDPRelayServer("91.151.16.62", 8888)


def shutdown(signum, frame):
    logging.info("Shutting down UDPRelayServer...")
    server.shutdown()
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

server.start()
server.join()
