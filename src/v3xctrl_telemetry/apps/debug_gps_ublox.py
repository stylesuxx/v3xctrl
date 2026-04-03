"""
GPS debug script - reads position, satellite, and RF status from a u-blox M10 module.

Enables additional diagnostic messages in RAM only (flash config is not modified).

Usage:
    python -m v3xctrl_telemetry.apps.debug_gps_ublox [--path /dev/serial0]

Press Ctrl-C to stop.

Tip: if satellite acquisition is slow, stop video streaming while running this script.
LTE transmission can interfere with GPS reception at the L1 frequency (1575 MHz).
"""

import argparse
import logging
import signal
import sys
import time
import types
from enum import IntEnum

import serial
from pyubx2 import ERR_IGNORE, SET_LAYER_RAM, TXN_NONE, UBXMessage, UBXReader

from v3xctrl_telemetry.UBXGpsTelemetry import UBXMessageId

logging.basicConfig(level=logging.DEBUG, format="%(message)s")
logger = logging.getLogger("gps_debug")

GPS_PATH = "/dev/serial0"
POLL_BAUDRATES = (115200, 9600)
BAUD_DETECT_TIMEOUT_S = 1.5
SERIAL_TIMEOUT = 0.1
ACK_TIMEOUT_S = 2.0

# Enables NAV-SAT and MON-RF in addition to NAV-PVT, at 1 Hz.
# Written to RAM only - flash is untouched and restored on power cycle.
DEBUG_CONFIG = {
    "CFG_UART1OUTPROT_UBX": 1,
    "CFG_UART1OUTPROT_NMEA": 0,
    "CFG_MSGOUT_UBX_NAV_PVT_UART1": 1,
    "CFG_MSGOUT_UBX_NAV_SAT_UART1": 1,
    "CFG_MSGOUT_UBX_MON_RF_UART1": 1,
    "CFG_RATE_MEAS": 1000,  # 1 Hz
}

WARN_CN0_MIN = 25  # dBHz - below this for a used satellite is poor signal
WARN_JAM_MAX = 50  # 0-255 - above this is a jamming concern
WARN_SAT_DROP = 2  # warn if numSV drops by this many or more in one cycle


class SatHealth(IntEnum):
    UNKNOWN = 0
    HEALTHY = 1
    UNHEALTHY = 2


GNSS_NAMES = {0: "GPS", 1: "SBAS", 2: "GAL", 3: "BDS", 4: "IMES", 5: "QZSS", 6: "GLO"}
ANT_STATUS = {0: "Initializing", 1: "Unknown", 2: "OK", 3: "Short", 4: "Open"}
ANT_POWER = {0: "Off", 1: "On", 2: "Unknown"}
JAM_STATE = {0: "Unknown", 1: "OK", 2: "Warning", 3: "Critical"}
FIX_NAMES = {
    0: "No Fix",
    1: "Dead Reckoning",
    2: "2D Fix",
    3: "3D Fix",
    4: "GNSS+Dead Reckoning",
    5: "Time Only",
}


def format_timestamp() -> str:
    now = time.time()
    return f"[{time.strftime('%H:%M:%S')}.{int(now % 1 * 1000):03d}]"


class GpsDebug:
    def __init__(self, path: str) -> None:
        self.path = path
        self.running = True
        self.prev_sats = 0
        self.ever_had_fix = False

    def stop(self, _sig: int, _frame: types.FrameType | None) -> None:
        self.running = False

    def get_port_at_baud(self, baudrate: int) -> serial.Serial | None:
        port = serial.Serial(self.path, baudrate, timeout=BAUD_DETECT_TIMEOUT_S)
        try:
            port.reset_input_buffer()
            # 256 bytes is enough to capture the UBX sync header (\xb5\x62) in the module's output burst
            raw = port.read(256)
            if b"\xb5\x62" in raw:
                return port

        except OSError:
            pass

        port.close()

        return None

    def apply_debug_config(self, port: serial.Serial) -> None:
        port.timeout = SERIAL_TIMEOUT
        cfg = UBXMessage.config_set(SET_LAYER_RAM, TXN_NONE, list(DEBUG_CONFIG.items()))
        port.write(cfg.serialize())
        port.flush()

        reader = UBXReader(port, quitonerror=ERR_IGNORE)
        deadline = time.monotonic() + ACK_TIMEOUT_S
        while time.monotonic() < deadline and self.running:
            _, msg = reader.read()
            if msg is None:
                continue

            match msg.identity:
                case UBXMessageId.ACK_ACK:
                    logger.info(
                        f"{format_timestamp()} Config applied (RAM only - flash unchanged, reverts on power cycle)"
                    )
                    return
                case UBXMessageId.ACK_NAK:
                    logger.warning(f"{format_timestamp()} [WARN] Module rejected debug config")
                    return

        logger.warning(f"{format_timestamp()} [WARN] No ACK received for debug config write")

    def open_port(self) -> serial.Serial:
        for baudrate in POLL_BAUDRATES:
            port = self.get_port_at_baud(baudrate)
            if port is not None:
                logger.info(f"{format_timestamp()} UBX sync found at {baudrate} baud on {self.path}")
                self.apply_debug_config(port)

                return port

        logger.warning(f"{format_timestamp()} [WARN] No UBX sync at 115200 baud, opening at 9600 without debug config")
        return serial.Serial(self.path, POLL_BAUDRATES[-1], timeout=SERIAL_TIMEOUT)

    def handle_nav_position_velocity_time(self, msg: UBXMessage) -> None:
        fix_type = msg.fixType
        num_sv = msg.numSV
        fix_name = FIX_NAMES.get(fix_type, f"UNK({fix_type})")

        pos = "lat=--  lon=--  speed=--"
        if fix_type >= 2:
            self.ever_had_fix = True
            pos = f"lat={msg.lat:.6f}  lon={msg.lon:.6f}  speed={msg.gSpeed * 3.6 / 1000:.1f} km/h"

        logger.info(f"{format_timestamp()} POSITION [NAV-PVT]  fix={fix_name}  satellites={num_sv}  {pos}")

        if (self.prev_sats - num_sv) >= WARN_SAT_DROP:
            logger.warning(f"{format_timestamp()} [WARN] satellites dropped {self.prev_sats} -> {num_sv}")

        if fix_type not in FIX_NAMES:
            logger.warning(f"{format_timestamp()} [WARN] unexpected fixType={fix_type}")

        self.prev_sats = int(num_sv)

    def handle_nav_satellites(self, msg: UBXMessage) -> None:
        satellite_count = msg.numSvs
        used_parts: list[str] = []
        seen_count: int = 0
        seen_max_cno: int = 0
        unhealthy_parts: list[str] = []
        weak_sat_count = 0

        for i in range(1, satellite_count + 1):
            gnss_id = getattr(msg, f"gnssId_{i:02d}", None)
            if gnss_id is None:
                continue

            sv_id = getattr(msg, f"svId_{i:02d}", None)
            cno = getattr(msg, f"cno_{i:02d}", None)
            elev = getattr(msg, f"elev_{i:02d}", None)
            sv_used = bool(getattr(msg, f"svUsed_{i:02d}", 0))
            health = getattr(msg, f"health_{i:02d}", 0)

            gnss_name = GNSS_NAMES.get(gnss_id, f"G{gnss_id}")

            if health == SatHealth.UNHEALTHY:
                unhealthy_parts.append(f"{gnss_name}{sv_id}({cno}dBHz {elev}°)")
            elif sv_used:
                used_parts.append(f"{gnss_name}{sv_id}({cno}dBHz {elev}°)")
                if cno is not None and cno < WARN_CN0_MIN:
                    weak_sat_count += 1
            else:
                seen_count += 1
                if cno is not None:
                    seen_max_cno = max(seen_max_cno, cno)

        indent = " " * 15
        used_count = len(used_parts)
        logger.info(f"{format_timestamp()} SATELLITES [NAV-SAT]  {used_count} used / {satellite_count} visible")
        logger.info(f"{indent}{'used:':<12}{' '.join(used_parts) or '(none)'}")
        if seen_count > 0:
            logger.info(f"{indent}{'seen:':<12}{seen_count} satellites")
        if unhealthy_parts:
            logger.info(f"{indent}{'unhealthy:':<12}{' '.join(unhealthy_parts)}")

        if weak_sat_count > 0:
            logger.warning(
                f"{format_timestamp()} [WARN] {weak_sat_count} used satellite(s)"
                f" below signal threshold ({WARN_CN0_MIN}dBHz)"
            )

        if not self.ever_had_fix and seen_count > 0 and seen_max_cno < WARN_CN0_MIN:
            logger.warning(
                f"{format_timestamp()} [WARN] No fix - strongest visible satellite only {seen_max_cno}dBHz,"
                f" below acquisition threshold ({WARN_CN0_MIN}dBHz) for ephemeris/almanac data"
            )

        logger.info("")

    def handle_monitor_rf(self, msg: UBXMessage) -> None:
        n_blocks = msg.nBlocks
        parts: list[str] = []
        warnings: list[str] = []

        for i in range(1, n_blocks + 1):
            ant_status: int | None = getattr(msg, f"antStatus_{i:02d}", None)
            ant_power: int | None = getattr(msg, f"antPower_{i:02d}", None)
            jam_ind: int | None = getattr(msg, f"jamInd_{i:02d}", None)
            gain: int | None = getattr(msg, f"agcCnt_{i:02d}", None)
            noise: int | None = getattr(msg, f"noisePerMS_{i:02d}", None)
            jam_state: int = getattr(msg, f"jammingState_{i:02d}", 0)

            ant_str = ANT_STATUS.get(ant_status, f"?{ant_status}") if ant_status is not None else "?"
            pwr_str = ANT_POWER.get(ant_power, f"?{ant_power}") if ant_power is not None else "?"
            jam_state_str = JAM_STATE.get(jam_state, f"?{jam_state}")
            parts.append(
                f"antenna={ant_str} power={pwr_str}"
                f" jamming={jam_ind}/255 state={jam_state_str} gain={gain} noise={noise}"
            )

            if ant_str in ("Short", "Open"):
                warnings.append(f"{format_timestamp()} [WARN] Antenna status: {ant_str}")

            if jam_ind is not None and jam_ind > WARN_JAM_MAX:
                warnings.append(f"{format_timestamp()} [WARN] Jamming indicator high: {jam_ind}/255")

            if jam_state_str in ("Warning", "Critical"):
                warnings.append(f"{format_timestamp()} [WARN] Jamming state: {jam_state_str}")

        logger.info(f"{format_timestamp()} RF-STATUS [MON-RF]  {' | '.join(parts)}")

        for warning in warnings:
            logger.warning(warning)

    def run(self) -> None:
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        try:
            port = self.open_port()
        except serial.SerialException as e:
            logger.error(f"Failed to open port: {e}")
            sys.exit(1)

        reader = UBXReader(port, quitonerror=ERR_IGNORE)
        logger.info("Waiting for messages... (Ctrl-C to stop)")
        logger.info("-" * 80)

        with port:
            while self.running:
                try:
                    _, msg = reader.read()
                except serial.SerialException as e:
                    logger.error(f"Serial port error: {e}")
                    break

                if msg is None:
                    continue

                match msg.identity:
                    case UBXMessageId.NAV_PVT:
                        self.handle_nav_position_velocity_time(msg)
                    case UBXMessageId.NAV_SAT:
                        self.handle_nav_satellites(msg)
                    case UBXMessageId.MON_RF:
                        self.handle_monitor_rf(msg)
                    case identity if identity.startswith(UBXMessageId.INF_PREFIX):
                        logger.info(f"{format_timestamp()} {identity}: {getattr(msg, 'msgContent', identity)}")

        logger.info("-" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(description="GPS debug script - position, satellites, and RF status")
    parser.add_argument("--path", default=GPS_PATH, help="Serial port path (default: /dev/serial0)")
    args = parser.parse_args()

    logger.info(f"Opening {args.path}...")
    GpsDebug(args.path).run()


if __name__ == "__main__":
    main()
