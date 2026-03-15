import argparse
import logging
import signal
import sys
import time
import traceback
import types
from v3xctrl_control import Server, State
from v3xctrl_control.message import Telemetry, Control

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG)

parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("port", type=int, help="The target port number")
args = parser.parse_args()

PORT = args.port

running = True


def telemetry_handler(message: Telemetry, addr: tuple[str, int]) -> None:
    values = message.get_values()
    logger.debug(f"Received telemetry message: {values}")


def disconnect_handler() -> None:
    """TODO: Implement disconnect handling."""
    logger.debug("Disconnected from client...")


def signal_handler(sig: int, frame: types.FrameType | None) -> None:
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
        server.send(Control({"ste": 50, "thr": 0}))

        time.sleep(10)

except Exception as e:
    logger.error(f"An error occurred: {e}")
    traceback.print_exc()

finally:
    server.stop()
    server.join()
    sys.exit(0)
