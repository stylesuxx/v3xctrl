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
import subprocess
import sys
import time
import traceback
import types
from concurrent.futures import ThreadPoolExecutor

from rpi_servo_pwm import HardwarePWM

from v3xctrl_control import Client, MixerType, State, esc_pulse_width, map_range, mix_differential
from v3xctrl_control.message import (
    Command,
    Control,
    Latency,
    PeerAnnouncement,
    Telemetry,
)
from v3xctrl_control.Telemetry import Telemetry as TelemetryHandler
from v3xctrl_gst import ControlClient
from v3xctrl_helper import Address, apply_expo, clamp
from v3xctrl_tcp import Transport
from v3xctrl_tcp.TcpTunnel import TcpTunnel
from v3xctrl_telemetry import GpsProtocol

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("host", help="The target IP address")
parser.add_argument("port", type=int, help="The target port number")
parser.add_argument("bind_port", type=int, help="The internal port number")

parser.add_argument(
    "--mixer-type",
    type=str,
    default="ackermann",
    choices=["ackermann", "differential"],
    help="How throttle and steering are combined into the two available PWM outputs (default: ackermann)",
)

# Ackermann mixer settings
parser.add_argument("--ackermann-throttle-min", type=int, default=1000, help="Ackermann throttle min (default: 1000)")
parser.add_argument("--ackermann-throttle-idle", type=int, default=1500, help="Ackermann throttle idle (default: 1500)")
parser.add_argument("--ackermann-throttle-max", type=int, default=2000, help="Ackermann throttle max (default: 2000)")
parser.add_argument(
    "--ackermann-throttle-failsafe", type=int, default=1500, help="Ackermann throttle failsafe (default: 1500)"
)
parser.add_argument(
    "--ackermann-throttle-scale-forward", type=int, default=100, help="Ackermann throttle forward scale (default: 100)"
)
parser.add_argument(
    "--ackermann-throttle-scale-reverse", type=int, default=100, help="Ackermann throttle reverse scale (default: 100)"
)
parser.add_argument(
    "--ackermann-throttle-min-forward", type=int, default=0, help="Ackermann throttle dead-zone forward (default: 0)"
)
parser.add_argument(
    "--ackermann-throttle-min-reverse", type=int, default=0, help="Ackermann throttle dead-zone reverse (default: 0)"
)
parser.add_argument("--ackermann-throttle-expo", type=int, default=0, help="Ackermann throttle expo (default: 0)")

parser.add_argument("--ackermann-steering-min", type=int, default=1000, help="Ackermann steering min (default: 1000)")
parser.add_argument("--ackermann-steering-max", type=int, default=2000, help="Ackermann steering max (default: 2000)")
parser.add_argument(
    "--ackermann-steering-failsafe", type=int, default=1500, help="Ackermann steering failsafe (default: 1500)"
)
parser.add_argument("--ackermann-steering-trim", type=int, default=0, help="Ackermann steering trim (default: 0)")
parser.add_argument("--ackermann-steering-scale", type=int, default=100, help="Ackermann steering scale (default: 100)")
parser.add_argument(
    "--ackermann-steering-invert", action="store_true", help="Ackermann steering invert (default: False)"
)
parser.add_argument("--ackermann-steering-expo", type=int, default=0, help="Ackermann steering expo (default: 0)")

# Differential mixer settings
parser.add_argument("--differential-motor-min", type=int, default=1000, help="Differential motor min (default: 1000)")
parser.add_argument("--differential-motor-idle", type=int, default=1500, help="Differential motor idle (default: 1500)")
parser.add_argument("--differential-motor-max", type=int, default=2000, help="Differential motor max (default: 2000)")
parser.add_argument(
    "--differential-motor-failsafe", type=int, default=1500, help="Differential motor failsafe (default: 1500)"
)
parser.add_argument(
    "--differential-motor-scale-forward", type=int, default=100, help="Differential motor forward scale (default: 100)"
)
parser.add_argument(
    "--differential-motor-scale-reverse", type=int, default=100, help="Differential motor reverse scale (default: 100)"
)
parser.add_argument(
    "--differential-motor-min-forward", type=int, default=0, help="Differential motor dead-zone forward (default: 0)"
)
parser.add_argument(
    "--differential-motor-min-reverse", type=int, default=0, help="Differential motor dead-zone reverse (default: 0)"
)
parser.add_argument("--differential-motor-expo", type=int, default=0, help="Differential motor expo (default: 0)")
parser.add_argument(
    "--differential-motor-reversible",
    action="store_true",
    help="Differential motors support reverse (default: False)",
)

parser.add_argument(
    "--differential-mixing-scale", type=int, default=100, help="Differential mixing scale (default: 100)"
)
parser.add_argument(
    "--differential-mixing-invert", action="store_true", help="Differential mixing invert (default: False)"
)
parser.add_argument("--differential-mixing-expo", type=int, default=0, help="Differential mixing expo (default: 0)")
parser.add_argument(
    "--differential-mixing-balance", type=int, default=0, help="Differential motor balance offset (default: 0)"
)

# PWM channel mapping
parser.add_argument("--pwm-channel-a", type=int, default=0, help="PWM channel A (default: 0)")
parser.add_argument("--pwm-channel-b", type=int, default=1, help="PWM channel B (default: 1)")

parser.add_argument(
    "--modem-path", type=str, default="/dev/ttyACM0", help="Path to modem device (default: /dev/ttyACM0)"
)
parser.add_argument(
    "--log", default="ERROR", help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). (default: ERROR)"
)
parser.add_argument(
    "--transport", type=str, default="udp", choices=["udp", "tcp"], help="Transport protocol (default: udp)"
)
parser.add_argument(
    "--relay-session-id",
    type=str,
    default=None,
    help="Relay session ID (enables relay TCP mode with PeerAnnouncement handshake)",
)
parser.add_argument(
    "--failsafe-ms", type=int, default=500, help="Timeout in milliseconds to trigger failsafe (default: 500)"
)
parser.add_argument("--battery-min-voltage", type=int, default=3500, help="Minimum cell voltage in mV (default: 3500)")
parser.add_argument("--battery-max-voltage", type=int, default=4200, help="Maximum cell voltage in mV (default: 4200)")
parser.add_argument("--battery-warn-voltage", type=int, default=3700, help="Warning cell voltage in mV (default: 3700)")
parser.add_argument(
    "--battery-i2c-address",
    type=lambda x: int(x, 0),
    default=0x40,
    help="I2C address of battery sensor (default: 0x40)",
)
parser.add_argument(
    "--battery-shunt-mohms", type=int, default=100, help="Shunt resistor value in milliohms (default: 100)"
)
parser.add_argument(
    "--battery-max-current", type=float, default=0.8, help="Maximum expected current in Amperes (default: 0.8)"
)
parser.add_argument(
    "--gps-path", type=str, default="/dev/serial0", help="Path to GPS UART device (default: /dev/serial0)"
)
parser.add_argument(
    "--gps-rate-hz",
    type=int,
    default=5,
    help="GPS NAV-PVT output rate in Hz (default: 5)",
)
parser.add_argument(
    "--gps-protocol",
    type=str,
    default="ublox",
    choices=["ublox", "nmea", "modem"],
    help="GPS module protocol (default: ublox)",
)


args = parser.parse_args()

HOST = args.host
PORT = args.port
BIND_PORT = args.bind_port

mixer_type = MixerType(args.mixer_type)
modem_path = args.modem_path
failsafe_ms = args.failsafe_ms

pwm_channel_a = args.pwm_channel_a
pwm_channel_b = args.pwm_channel_b

level_name = args.log.upper()
level = getattr(logging, level_name, None)

if not isinstance(level, int):
    raise ValueError(f"Invalid log level: {args.log}")

logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")

# Ackermann mixer variables
ackermann_throttle_min = args.ackermann_throttle_min
ackermann_throttle_idle = args.ackermann_throttle_idle
ackermann_throttle_max = args.ackermann_throttle_max
ackermann_throttle_failsafe = args.ackermann_throttle_failsafe
ackermann_throttle_scale_forward = args.ackermann_throttle_scale_forward
ackermann_throttle_scale_reverse = args.ackermann_throttle_scale_reverse
ackermann_throttle_min_forward = args.ackermann_throttle_min_forward
ackermann_throttle_min_reverse = args.ackermann_throttle_min_reverse
ackermann_throttle_expo = args.ackermann_throttle_expo

ackermann_steering_min = args.ackermann_steering_min
ackermann_steering_max = args.ackermann_steering_max
ackermann_steering_failsafe = args.ackermann_steering_failsafe
ackermann_steering_trim = args.ackermann_steering_trim
ackermann_steering_scale = args.ackermann_steering_scale
ackermann_steering_invert = args.ackermann_steering_invert
ackermann_steering_expo = args.ackermann_steering_expo

ackermann_forward_min = ackermann_throttle_idle + ackermann_throttle_min_forward
ackermann_reverse_min = ackermann_throttle_idle - ackermann_throttle_min_reverse
ackermann_forward_multiplier = ackermann_throttle_scale_forward / 100.0
ackermann_reverse_multiplier = ackermann_throttle_scale_reverse / 100.0
ackermann_steering_multiplier = ackermann_steering_scale / 100.0

ackermann_steering_left = -1
ackermann_steering_right = 1
ackermann_trim_multiplier = 1

if ackermann_steering_invert:
    ackermann_steering_left = 1
    ackermann_steering_right = -1
    ackermann_trim_multiplier = -1

# Differential mixer variables
differential_motor_min = args.differential_motor_min
differential_motor_idle = args.differential_motor_idle
differential_motor_max = args.differential_motor_max
differential_motor_failsafe = args.differential_motor_failsafe
differential_motor_scale_forward = args.differential_motor_scale_forward
differential_motor_scale_reverse = args.differential_motor_scale_reverse
differential_motor_min_forward = args.differential_motor_min_forward
differential_motor_min_reverse = args.differential_motor_min_reverse
differential_motor_expo = args.differential_motor_expo
differential_motor_reversible = args.differential_motor_reversible

differential_mixing_scale = args.differential_mixing_scale
differential_mixing_invert = args.differential_mixing_invert
differential_mixing_expo = args.differential_mixing_expo
differential_mixing_balance = args.differential_mixing_balance

differential_forward_min = differential_motor_idle + differential_motor_min_forward
differential_reverse_min = differential_motor_idle - differential_motor_min_reverse
differential_forward_multiplier = differential_motor_scale_forward / 100.0
differential_reverse_multiplier = differential_motor_scale_reverse / 100.0
differential_mixing_multiplier = differential_mixing_scale / 100.0

differential_mixing_invert_multiplier = 1
if differential_mixing_invert:
    differential_mixing_invert_multiplier = -1

running = True
received_command_ids: set[str] = set()

pwm_throttle = HardwarePWM(pwm_channel_a)
pwm_steering = HardwarePWM(pwm_channel_b)


def calculate_ackermann_steering_center() -> int:
    center = (ackermann_steering_max + ackermann_steering_min) / 2 + ackermann_steering_trim
    return int(max(ackermann_steering_min, min(ackermann_steering_max, center)))


if mixer_type == MixerType.ACKERMANN:
    steering_center = calculate_ackermann_steering_center()
    channel_b_idle = steering_center
    channel_a_idle = ackermann_throttle_idle
else:
    steering_center = 0
    channel_b_idle = differential_motor_idle
    channel_a_idle = differential_motor_idle

pwm_throttle.setup(channel_a_idle)
pwm_steering.setup(channel_b_idle)

telemetry = TelemetryHandler(
    modem_path,
    battery_min_voltage=args.battery_min_voltage,
    battery_max_voltage=args.battery_max_voltage,
    battery_warn_voltage=args.battery_warn_voltage,
    battery_i2c_address=args.battery_i2c_address,
    battery_shunt_mohms=args.battery_shunt_mohms,
    battery_max_current=args.battery_max_current,
    gps_path=args.gps_path,
    gps_rate_hz=args.gps_rate_hz,
    gps_protocol=GpsProtocol(args.gps_protocol),
)
telemetry.start()

video_control = ControlClient()
executor = ThreadPoolExecutor(max_workers=2)


def control_handler(message: Control, address: Address) -> None:
    throttle_value: int = 0
    steering_value: int = 0

    if client.state == State.CONNECTED:
        values = message.get_values()
        raw_throttle = values["throttle"]
        raw_steering = values["steering"]

        match mixer_type:
            case MixerType.ACKERMANN:
                raw_throttle = apply_expo(raw_throttle, ackermann_throttle_expo)
                raw_steering = apply_expo(raw_steering, ackermann_steering_expo)

                throttle_value = esc_pulse_width(
                    raw_throttle,
                    ackermann_forward_min,
                    ackermann_throttle_max,
                    ackermann_throttle_min,
                    ackermann_reverse_min,
                    ackermann_forward_multiplier,
                    ackermann_reverse_multiplier,
                    ackermann_throttle_idle,
                    reversible=True,
                )

                scaled_steering = raw_steering * ackermann_steering_multiplier
                steering_value = int(
                    clamp(
                        map_range(
                            scaled_steering,
                            ackermann_steering_left,
                            ackermann_steering_right,
                            ackermann_steering_min,
                            ackermann_steering_max,
                        )
                        + (ackermann_steering_trim * ackermann_trim_multiplier),
                        ackermann_steering_min,
                        ackermann_steering_max,
                    )
                )

            case MixerType.DIFFERENTIAL:
                raw_throttle = apply_expo(raw_throttle, differential_motor_expo)
                raw_steering = apply_expo(raw_steering, differential_mixing_expo)

                signed_steering = raw_steering * differential_mixing_multiplier * differential_mixing_invert_multiplier
                left, right = mix_differential(raw_throttle, signed_steering)

                throttle_value = int(
                    clamp(
                        esc_pulse_width(
                            left,
                            differential_forward_min,
                            differential_motor_max,
                            differential_motor_min,
                            differential_reverse_min,
                            differential_forward_multiplier,
                            differential_reverse_multiplier,
                            differential_motor_idle,
                            reversible=differential_motor_reversible,
                        )
                        + differential_mixing_balance,
                        differential_motor_min,
                        differential_motor_max,
                    )
                )
                steering_value = int(
                    clamp(
                        esc_pulse_width(
                            right,
                            differential_forward_min,
                            differential_motor_max,
                            differential_motor_min,
                            differential_reverse_min,
                            differential_forward_multiplier,
                            differential_reverse_multiplier,
                            differential_motor_idle,
                            reversible=differential_motor_reversible,
                        )
                        - differential_mixing_balance,
                        differential_motor_min,
                        differential_motor_max,
                    )
                )
    else:
        match mixer_type:
            case MixerType.ACKERMANN:
                throttle_value = ackermann_throttle_failsafe
                steering_value = ackermann_steering_failsafe
            case MixerType.DIFFERENTIAL:
                throttle_value = differential_motor_failsafe
                steering_value = differential_motor_failsafe

    logger.debug(f"Throttle: {throttle_value}; Steering: {steering_value}")

    pwm_throttle.set_pulse_width(int(throttle_value))
    pwm_steering.set_pulse_width(int(steering_value))


def latency_handler(message: Latency, address: Address) -> None:
    client.send(Latency(st=time.time(), timestamp=message.timestamp))


def command_handler(command: Command, address: Address) -> None:
    """
    Commands are executed in the background, so we do not know (nor do we care)
    if they finish successfully.
    """
    command_id = command.get_command_id()
    if command_id in received_command_ids:
        return

    received_command_ids.add(command_id)
    logger.info(f"Received command: {command}")

    cmd = command.get_command()
    match cmd:
        case "service":
            parameters = command.get_parameters()
            action: str = parameters["action"]
            name: str = parameters["name"]
            subprocess.Popen(["sudo", "systemctl", action, name])

        case "recording":
            parameters = command.get_parameters()
            recording_action: str = parameters["action"]
            executor.submit(video_control.recording, recording_action)

        case "trim":
            global ackermann_steering_trim, steering_center, differential_mixing_balance

            parameters = command.get_parameters()
            trim_action: str = parameters["action"]
            step = 5

            match mixer_type:
                case MixerType.ACKERMANN:
                    if trim_action == "increase":
                        ackermann_steering_trim += step
                    else:
                        ackermann_steering_trim -= step

                    steering_center = calculate_ackermann_steering_center()
                    subprocess.Popen(
                        [
                            "sudo",
                            "v3xctrl-settings",
                            "set",
                            ".control.mixer.ackermann.steering.trim",
                            str(ackermann_steering_trim),
                        ]
                    )

                case MixerType.DIFFERENTIAL:
                    if trim_action == "increase":
                        differential_mixing_balance += step
                    else:
                        differential_mixing_balance -= step

                    subprocess.Popen(
                        [
                            "sudo",
                            "v3xctrl-settings",
                            "set",
                            ".control.mixer.differential.mixing.balance",
                            str(differential_mixing_balance),
                        ]
                    )

        case "shutdown":
            subprocess.Popen(["sudo", "poweroff"])

        case "restart":
            subprocess.Popen(["sudo", "reboot", "-f"])

        case _:
            logger.error(f"Unknown command: {command}")


def disconnect_handler() -> None:
    """
    Disconnect counts as failsafe, set values accordingly
    """

    match mixer_type:
        case MixerType.ACKERMANN:
            pwm_throttle.set_pulse_width(ackermann_throttle_failsafe)
            pwm_steering.set_pulse_width(ackermann_steering_failsafe)
        case MixerType.DIFFERENTIAL:
            pwm_throttle.set_pulse_width(differential_motor_failsafe)
            pwm_steering.set_pulse_width(differential_motor_failsafe)

    logger.info("Disconnected")


def connect_handler() -> None:
    logger.info("Connected")


def signal_handler(sig: int, frame: types.FrameType | None) -> None:
    global running
    if running:
        running = False


def cleanup_pwm() -> None:
    # An attempt to cleanly shut down PWM without making Servo/ESC freak out and
    # switch to max positions. The idea here is the following:
    # 1. Set a known save state for some time
    # 2. Set to 0 pulse width for some time
    # 3. Disable and close
    #
    # Setting for 0 pulse width for some reason seems to work really well to not
    # make the servo/ESC act up when disabling and closing PWM.
    channel_b_idle = channel_a_idle if mixer_type == MixerType.DIFFERENTIAL else steering_center

    pwm_throttle.set_pulse_width(channel_a_idle)
    pwm_steering.set_pulse_width(channel_b_idle)
    time.sleep(1)

    pwm_throttle.set_pulse_width(0)
    pwm_steering.set_pulse_width(0)
    time.sleep(1)

    pwm_throttle.disable()
    pwm_steering.disable()

    pwm_throttle.close()
    pwm_steering.close()


tcp_tunnel = None
if args.transport == Transport.TCP:
    handshake = None
    if args.relay_session_id:
        handshake = PeerAnnouncement(r="streamer", i=args.relay_session_id, p="control").to_bytes()

    tcp_tunnel = TcpTunnel(
        remote_host=HOST,
        remote_port=PORT,
        local_component_port=BIND_PORT,
        bidirectional=True,
        handshake=handshake,
    )
    tcp_tunnel.start()
    ephemeral_port = tcp_tunnel.wait_for_port()
    if ephemeral_port is None:
        logger.error("Failed to allocate TCP tunnel port")
        sys.exit(1)
    HOST = "127.0.0.1"
    PORT = ephemeral_port
    logger.info(f"TCP tunnel: control -> 127.0.0.1:{ephemeral_port} -> TCP -> {args.host}:{args.port}")

# In default UDP mode, mind to external interface, in TCP mode, bind to local
# interface to which TCP proxy will forward the packages
bind_address = "0.0.0.0"
if args.transport == Transport.TCP:
    bind_address = "127.0.0.1"

client = Client(HOST, PORT, BIND_PORT, failsafe_ms, bind_address=bind_address)

# Subscribe to messages received from the server
client.subscribe(Control, control_handler)
client.subscribe(Latency, latency_handler)
client.subscribe(Command, command_handler)

# Subscribe to life-cycle events
client.on(State.DISCONNECTED, disconnect_handler)
client.on(State.CONNECTED, connect_handler)

client.start()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Telemetry update loop
try:
    while running:
        # Only send telemetry if connected
        if client.state == State.CONNECTED:
            telemetry_data = telemetry.get_telemetry()
            telemetry_message = Telemetry(telemetry_data)
            client.send(telemetry_message)

        time.sleep(1)

except Exception as e:
    logger.error(f"An error occurred: {e}")
    traceback.print_exc()

finally:
    executor.shutdown(wait=False)

    client.stop()
    telemetry.stop()

    if tcp_tunnel:
        tcp_tunnel.stop()

    client.join()
    telemetry.join()

    cleanup_pwm()
    logger.info("cleaned up.")

    sys.exit(0)
