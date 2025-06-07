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

from v3xctrl_control import Client, State
from v3xctrl_control.Telemetry import Telemetry as TelemetryHandler
from v3xctrl_control.Message import Control, Telemetry, Latency

from v3xctrl_helper import clamp

parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("host", help="The target IP address")
parser.add_argument("port", type=int, help="The target port number")
parser.add_argument("bind_port", type=int, help="The internal port number")

parser.add_argument("--throttle-min", type=int, default=1000,
                    help="Minimum pulse width for throttle (default: 1000)")
parser.add_argument("--throttle-idle", type=int, default=1500,
                    help="Mid pulse width for throttle (default: 1500)")
parser.add_argument("--throttle-max", type=int, default=2000,
                    help="Maximum pulse width for throttle (default: 2000)")
parser.add_argument("--steering-min", type=int, default=1000,
                    help="Minimum pulse width for steering (default: 1000)")
parser.add_argument("--steering-max", type=int, default=2000,
                    help="Maximum pulse width for steering (default: 2000)")
parser.add_argument("--steering-trim", type=int, default=0,
                    help="Pulse width to trim steering center (default: 0)")
parser.add_argument("--steering-invert", action="store_true",
                    help="Invert steering direction (default: False)")
parser.add_argument("--steering-scale", type=int, default=100,
                    help="Max percent of range for steering (default: 100)")
parser.add_argument("--forward-scale", type=int, default=100,
                    help="Max percent of range for forward throttle (default: 100)")
parser.add_argument("--reverse-scale", type=int, default=100,
                    help="Max percent of range for reverse throttle (default: 100)")
parser.add_argument("--forward-boost", type=int, default=0,
                    help="Minimum pulse width offset for going forward (default: 0)")
parser.add_argument("--reverse-boost", type=int, default=0,
                    help="Minimum pulse width offset for going reverse (default: 0)")
parser.add_argument("--gpio-throttle", type=int, default=18,
                    help="GPIO pin number for throttle signal (default: 18)")
parser.add_argument("--gpio-steering", type=int, default=13,
                    help="GPIO pin number for steering signal (default: 13)")
parser.add_argument("--modem-path", type=str, default="/dev/ttyACM0",
                    help="Path to modem device (default: /dev/ttyACM0)")
parser.add_argument("--log", default="ERROR",
                    help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). (default: ERROR")

args = parser.parse_args()

HOST = args.host
PORT = args.port
BIND_PORT = args.bind_port

throttle_min = args.throttle_min
throttle_idle = args.throttle_idle
throttle_max = args.throttle_max
forward_scale = args.forward_scale
reverse_scale = args.reverse_scale

forward_boost = args.forward_boost
reverse_boost = args.reverse_boost

forward_min = throttle_idle + forward_boost
reverse_min = throttle_idle - reverse_boost

steering_min = args.steering_min
steering_max = args.steering_max
steering_trim = args.steering_trim
steering_invert = args.steering_invert
steering_scale = args.steering_scale

throttle_gpio = args.gpio_throttle
steering_gpio = args.gpio_steering

modem_path = args.modem_path

level_name = args.log.upper()
level = getattr(logging, level_name, None)

if not isinstance(level, int):
    raise ValueError(f"Invalid log level: {args.log}")

logging.basicConfig(
    level=level,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

forward_multiplier = forward_scale / 100.0
reverse_multiplier = reverse_scale / 100.0
steering_multiplier = steering_scale / 100.0

steering_left = -1
steering_right = 1
trim_multiplier = 1

if steering_invert:
    steering_left = 1
    steering_right = -1
    trim_multiplier = -1

running = True

pi = pigpio.pi()
pi.set_mode(throttle_gpio, pigpio.OUTPUT)
pi.set_mode(steering_gpio, pigpio.OUTPUT)

steering_center = (steering_max + steering_min) / 2 + steering_trim
# Clamp result between defined min/max pulewidth
steering_center = max(steering_min, min(steering_max, steering_center))

pi.set_servo_pulsewidth(throttle_gpio, throttle_idle)
pi.set_servo_pulsewidth(steering_gpio, steering_center)

telemetry = TelemetryHandler(modem_path)
telemetry.start()


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

    clamped = clamp(value, in_min, in_max)
    normalized = (clamped - in_min) / (in_max - in_min)
    return int(servo_min + normalized * (servo_max - servo_min))


def control_handler(message: Control) -> None:
    values = message.get_values()
    raw_throttle = values['throttle']
    raw_steering = values['steering']

    # Determine throttle pulse forward or reverse
    if raw_throttle > 0:
        scaled_throttle = raw_throttle * forward_multiplier
        throttle_value = map_range(scaled_throttle, 0, 1, forward_min, throttle_max)
    else:
        scaled_throttle = raw_throttle * reverse_multiplier
        throttle_value = map_range(scaled_throttle, -1, 0, throttle_min, reverse_min)

    # Map, add trim and clamp
    scaled_steering = raw_steering * steering_multiplier
    steering_value = map_range(scaled_steering, steering_left, steering_right, steering_min, steering_max) + (steering_trim * trim_multiplier)
    steering_value = clamp(steering_value, steering_min, steering_max)

    logging.debug(f"Throttle: {throttle_value}; Steering: {steering_value}")

    pi.set_servo_pulsewidth(throttle_gpio, throttle_value)
    pi.set_servo_pulsewidth(steering_gpio, steering_value)


def latency_handler(message: Latency) -> None:
    client.send(message)


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


client = Client(HOST, PORT, BIND_PORT)

# Subscribe to messages received from the server
client.subscribe(Control, control_handler)
client.subscribe(Latency, latency_handler)

# Subscribe to life-cycle events
client.on(State.DISCONNECTED, disconnect_handler)

client.start()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

try:
    while running:
        # Only send telemetry if connected
        if client.state == State.CONNECTED:
            telemetry_data = telemetry.get_telemetry()
            telemetry_message = Telemetry(telemetry_data)
            client.send(telemetry_message)

        time.sleep(1)

except Exception as e:
    logging.error(f"An error occurred: {e}")
    traceback.print_exc()

finally:

    client.stop()
    telemetry.stop()

    client.join()
    telemetry.join()

    pi.set_servo_pulsewidth(throttle_gpio, 0)
    pi.set_servo_pulsewidth(steering_gpio, 0)
    pi.stop()

    sys.exit(0)
