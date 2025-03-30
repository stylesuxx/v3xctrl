import argparse
import logging
import signal
import sys
import time
import traceback

from rpi_4g_streamer import Server, State
from rpi_4g_streamer.Message import Telemetry, Control


logging.basicConfig(level=logging.DEBUG)

parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("port", type=int, help="The target port number")
args = parser.parse_args()

PORT = args.port

running = True


def telemetry_handler(message: Telemetry) -> None:
    """ TODO: Implement control message handling. """
    values = message.get_values()
    logging.debug(f"Received telemetry message: {values}")


def disconnect_handler() -> None:
    """ TODO: Implement disconnect handling. """
    logging.debug("Disconnected from client...")


def signal_handler(sig, frame):
    global running
    if running:
        running = False
        print("Shutting down...")


server = Server(PORT)

# Subscribe to messages received from the client
server.subscribe(Telemetry, telemetry_handler)

# Subscribe to life-cycle events
server.on(State.DISCONNECTED, disconnect_handler)

server.start()

signal.signal(signal.SIGINT, signal_handler)

try:
    while running:
        """ TODO: Implement your functionality to communicat with the server. """
        server.send(Control({
            "ste": 50,
            "thr": 0
        }))

        time.sleep(10)

except Exception as e:
    logging.error(f"An error occurred: {e}")
    traceback.print_exc()

finally:
    server.stop()
    server.join()
    sys.exit(0)
