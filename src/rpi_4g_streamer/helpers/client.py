"""
This file is intended to be expanded with your custom functionality. It is
barebone right now, just subscribing to Control messages.

Here you would add your own functionality to process those messages, set servos,
blink lights, etc.

CTRL-C will exit the client cleanly
"""
import argparse
import logging
import signal
import sys
import time
import traceback

from rpi_4g_streamer import Client, Control, Telemetry, State


logging.basicConfig(level=logging.DEBUG)

parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("host", help="The target IP address")
parser.add_argument("port", type=int, help="The target port number")
args = parser.parse_args()

HOST = args.host
PORT = args.port

running = True


def control_handler(message: Control) -> None:
    """ TODO: Implement control message handling. """
    values = message.get_values()
    logging.debug(f"Received control message: {values}")


def disconnect_handler() -> None:
    """ TODO: Implement disconnect handling. """
    logging.debug("Disconnected from server...")


def signal_handler(sig, frame):
    global running
    running = False
    print("Shutting down...")


client = Client(HOST, PORT)

# Subscribe to messages received from the server
client.subscribe(Control, control_handler)

# Subscribe to life-cycle events
client.on(State.DISCONNECTED, disconnect_handler)

client.start()

signal.signal(signal.SIGINT, signal_handler)

try:
    while running:
        """ TODO: Implement your functionality to communicat with the server. """
        client.send(Telemetry({
            'key_1': 69
        }))

        time.sleep(10)

except Exception as e:
    logging.error(f"An error occurred: {e}")
    traceback.print_exc()

finally:
    client.stop()
    client.join()
    sys.exit(0)
