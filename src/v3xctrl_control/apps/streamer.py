"""
This file is intended to be expanded with your custom functionality. It is
barebone right now, just subscribing to Control messages.

Here you would add your own functionality to process those messages, set servos,
blink lights, etc.

CTRL-C will exit the client cleanly
"""
import argparse
import logging
from rpi_servo_pwm import HardwarePWM
import signal
import subprocess
import sys
import time
import traceback
import types
from typing import cast

from v3xctrl_control import Client, State
from v3xctrl_control.Telemetry import Telemetry as TelemetryHandler
from v3xctrl_control.Message import (
  Message,
  Command,
  Control,
  Telemetry,
  Latency,
)

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
parser.add_argument("--pwm-channel-throttle", type=int, default=0,
                    help="PWM channel for throttle signal (default: 0)")
parser.add_argument("--pwm-channel-steering", type=int, default=1,
                    help="PWM channel for steering signal (default: 1)")
parser.add_argument("--modem-path", type=str, default="/dev/ttyACM0",
                    help="Path to modem device (default: /dev/ttyACM0)")
parser.add_argument("--log", default="ERROR",
                    help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). (default: ERROR")
parser.add_argument("--failsafe-ms", type=int, default=500,
                    help="Timeout in milliseconds to trigger failsafe (default: 500)")
parser.add_argument("--failsafe-throttle", type=int, default=1500,
                    help="Throttle value when failsafe (default: 1500)")
parser.add_argument("--failsafe-steering", type=int, default=1500,
                    help="Steering value when failsafe (default: 1500)")


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

pwm_channel_throttle = args.pwm_channel_throttle
pwm_channel_steering = args.pwm_channel_steering

modem_path = args.modem_path

level_name = args.log.upper()
level = getattr(logging, level_name, None)

failsafe_ms = args.failsafe_ms
failsafe_throttle = args.failsafe_throttle
failsafe_steering = args.failsafe_steering

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
received_command_ids: set[str] = set()

pwm_throttle = HardwarePWM(pwm_channel_throttle)
pwm_steering = HardwarePWM(pwm_channel_steering)

steering_center = (steering_max + steering_min) / 2 + steering_trim
# Clamp result between defined min/max pulewidth
steering_center = max(steering_min, min(steering_max, steering_center))

pwm_throttle.setup(int(throttle_idle))
pwm_steering.setup(int(steering_center))

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


def control_handler(message: Message) -> None:
    message = cast(Control, message)
    throttle_value = failsafe_throttle
    steering_value = failsafe_steering

    if client.state == State.CONNECTED:
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
        steering_value = map_range(
            scaled_steering,
            steering_left,
            steering_right,
            steering_min,
            steering_max
        ) + (steering_trim * trim_multiplier)
        steering_value = clamp(steering_value, steering_min, steering_max)

    logging.debug(f"Throttle: {throttle_value}; Steering: {steering_value}")

    pwm_throttle.set_pulse_width(int(throttle_value))
    pwm_steering.set_pulse_width(int(steering_value))


def latency_handler(message: Message) -> None:
    message = cast(Latency, message)
    client.send(message)


def command_handler(command: Message) -> None:
    command = cast(Command, command)
    command_id = command.get_command_id()
    if command_id in received_command_ids:
        return

    received_command_ids.add(command_id)
    logging.debug(f"Received command: {command}")

    cmd = command.get_command()
    if cmd == "service":
        parameters = command.get_parameters()
        action: str = parameters["action"]
        name: str = parameters["name"]

        subprocess.run(["sudo", "systemctl", action, name])
    elif cmd == "shutdown":
        subprocess.run(["sudo", "shutdown", "now"])
    else:
        logging.error(f"Unknown command: {command}")


def disconnect_handler() -> None:
    """
    Disconnect counts as failsafe, set values accordingly
    """
    logging.debug("Disconnected from server...")

    pwm_throttle.set_pulse_width(int(throttle_idle))
    pwm_steering.set_pulse_width(int(steering_center))


def signal_handler(sig: int, frame: types.FrameType | None) -> None:
    global running
    if running:
        running = False


client = Client(HOST, PORT, BIND_PORT, failsafe_ms)

# Subscribe to messages received from the server
client.subscribe(Control, control_handler)
client.subscribe(Latency, latency_handler)
client.subscribe(Command, command_handler)

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

    pwm_throttle.disable()
    pwm_steering.disable()

    pwm_throttle.close()
    pwm_steering.close()

    sys.exit(0)
