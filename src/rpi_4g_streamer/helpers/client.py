"""
This file is intended to be expanded with your custom functionality. It is
barebone right now, just subscribing to Control messages.

Here you would add your own functionality to process those messages, set servos,
blink lights, etc.

CTRL-C will exit the client cleanly
"""
import argparse
import logging
import pigpio
import signal
import sys
import time
import traceback

from rpi_4g_streamer import Client, State
from rpi_4g_streamer.Message import Control, Telemetry

logging.basicConfig(level=logging.DEBUG)

parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("host", help="The target IP address")
parser.add_argument("port", type=int, help="The target port number")

parser.add_argument("--throttle-min", type=int, default=1000,
                    help="Minimum pulse width for throttle (default: 1000)")
parser.add_argument("--throttle-idle", type=int, default=1200,
                    help="Mid pulse width for throttle (default: 1200)")
parser.add_argument("--throttle-max", type=int, default=2000,
                    help="Maximum pulse width for throttle (default: 2000)")
parser.add_argument("--steering-min", type=int, default=1000,
                    help="Minimum pulse width for steering (default: 1000)")
parser.add_argument("--steering-max", type=int, default=2000,
                    help="Maximum pulse width for steering (default: 2000)")
parser.add_argument("--steering-trim", type=int, default=0,
                    help="Pulse width to trim steering center (default: 0)" )

args = parser.parse_args()

HOST = args.host
PORT = args.port

throttle_min = args.throttle_min
throttle_idle = args.throttle_idle
throttle_max = args.throttle_max
steering_min = args.steering_min
steering_max = args.steering_max
steering_trim = args.steering_trim

running = True

throttle_gpio = 18  # PWM0
steering_gpio = 13  # PWM1

pi = pigpio.pi()
pi.set_mode(throttle_gpio, pigpio.OUTPUT)
pi.set_mode(steering_gpio, pigpio.OUTPUT)

steering_center = (steering_max + steering_min) / 2 + steering_trim
# Clamp result between defined min/max pulewidth
steering_center = max(steering_min, min(steering_max, steering_center))

pi.set_servo_pulsewidth(throttle_gpio, throttle_idle)
pi.set_servo_pulsewidth(steering_gpio, steering_center)


def map_range(
    value: float,
    in_min: float, in_max: float,
    servo_min: int = 1000, servo_max: int = 2000
) -> int:
    """
    Maps a float value from an input range [in_min, in_max] to a servo PWM pulse width.

    Args:
        value: Input value to map.
        in_min: Minimum of input range.
        in_max: Maximum of input range.
        servo_min: Minimum servo pulse width in microseconds.
        servo_max: Maximum servo pulse width in microseconds.

    Returns:
        Mapped servo pulse width as integer in microseconds.
    """
    if in_min == in_max:
        raise ValueError("Input range cannot be zero")

    clamped = max(min(value, in_max), in_min)
    normalized = (clamped - in_min) / (in_max - in_min)
    return int(servo_min + normalized * (servo_max - servo_min))


def control_handler(message: Control) -> None:
    values = message.get_values()

    # Determine throttle pulse forward or reverse
    if values['throttle'] > 0:
        throttle_value = map_range(values['throttle'], 0, 1, throttle_idle, throttle_max)
    else:
        throttle_value = map_range(values['throttle'], -1, 0, throttle_min, throttle_idle)

    # Add steering trim to output
    steering_value = map_range(values['steering'], -1, 1, steering_min, steering_max) + steering_trim
    # Clamp result between defined min/max pulewidth
    steering_value = max(steering_min, min(steering_max, steering_value))

    logging.debug(f"Throttle: {throttle_value}; Steering: {steering_value}")

    pi.set_servo_pulsewidth(throttle_gpio, throttle_value)
    pi.set_servo_pulsewidth(steering_gpio, steering_value)


def disconnect_handler() -> None:
    """
    When disconnected:

    - Center servo
    - Min throttle
    """
    logging.debug("Disconnected from server...")
    pi.set_servo_pulsewidth(throttle_gpio, throttle_idle)
    pi.set_servo_pulsewidth(steering_gpio, steering_center)


def signal_handler(sig, frame):
    global running
    if running:
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
            'lat': 0,
            'lon': 0,
            'bar': 3,
            'qty': 3
        }))

        time.sleep(10)

except Exception as e:
    logging.error(f"An error occurred: {e}")
    traceback.print_exc()

finally:
    client.stop()
    client.join()
    sys.exit(0)
