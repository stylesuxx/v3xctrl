"""
GPS debug script - reads NAV-PVT, NAV-SAT, and MON-RF from a u-blox M10 module.

Enables additional diagnostic messages in RAM only (flash config is not modified).

Usage:
    python -m v3xctrl_telemetry.apps.debug_gps [--path /dev/serial0]

Press Ctrl-C to stop. A warning summary is printed on exit.

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
ANT_STATUS = {0: "INIT", 1: "UNKN", 2: "OK", 3: "SHORT", 4: "OPEN"}
ANT_POWER = {0: "OFF", 1: "ON", 2: "UNKN"}
JAM_STATE = {0: "unknown", 1: "ok", 2: "WARNING", 3: "CRITICAL"}
FIX_NAMES = {0: "NO_FIX", 1: "DR", 2: "2D", 3: "3D", 4: "GNSS+DR", 5: "TIME_ONLY"}


def format_timestamp() -> str:
    now = time.time()
    return f"[{time.strftime('%H:%M:%S')}.{int(now % 1 * 1000):03d}]"


def open_at_baud(path: str, baudrate: int) -> serial.Serial | None:
    port = serial.Serial(path, baudrate, timeout=BAUD_DETECT_TIMEOUT_S)
    try:
        port.reset_input_buffer()
        raw = port.read(256)
        if b"\xb5\x62" in raw:
            return port

    except OSError:
        pass

    port.close()
    return None


def apply_debug_config(port: serial.Serial, logger: logging.Logger) -> None:
    port.timeout = SERIAL_TIMEOUT
    cfg = UBXMessage.config_set(SET_LAYER_RAM, TXN_NONE, list(DEBUG_CONFIG.items()))
    port.write(cfg.serialize())
    port.flush()

    reader = UBXReader(port, quitonerror=ERR_IGNORE)
    deadline = time.monotonic() + ACK_TIMEOUT_S
    while time.monotonic() < deadline:
        _, msg = reader.read()
        if msg is None:
            continue

        match msg.identity:
            case UBXMessageId.ACK_ACK:
                logger.info(f"{format_timestamp()} Config applied (RAM only - flash unchanged, reverts on power cycle)")
                return
            case UBXMessageId.ACK_NAK:
                logger.warning(f"{format_timestamp()} [WARN] Module rejected debug config")
                return

    logger.warning(f"{format_timestamp()} [WARN] No ACK received for debug config write")


def open_port(path: str, logger: logging.Logger) -> serial.Serial:
    for baudrate in POLL_BAUDRATES:
        port = open_at_baud(path, baudrate)
        if port is not None:
            logger.info(f"{format_timestamp()} UBX sync found at {baudrate} baud on {path}")
            apply_debug_config(port, logger)
            return port
    logger.warning(f"{format_timestamp()} [WARN] No UBX sync at 115200 baud, opening at 9600 without debug config")
    return serial.Serial(path, POLL_BAUDRATES[-1], timeout=SERIAL_TIMEOUT)


def handle_nav_position_velocity_time(
    msg: UBXMessage, prev_sats: int | None, logger: logging.Logger, warn_count: list
) -> int:
    fix_type = msg.fixType
    num_sv = msg.numSV
    fix_name = FIX_NAMES.get(fix_type, f"UNK({fix_type})")

    pos = "lat=--  lon=--  speed=--"
    if fix_type >= 2:
        pos = f"lat={msg.lat:.6f}  lon={msg.lon:.6f}  speed={msg.gSpeed * 3.6 / 1000:.1f} km/h"

    logger.info(f"{format_timestamp()} NAV-PVT  fix={fix_name}  sats={num_sv}  {pos}")

    if prev_sats is not None and (prev_sats - num_sv) >= WARN_SAT_DROP:
        logger.warning(f"{format_timestamp()} [WARN] sats dropped {prev_sats} -> {num_sv}")
        warn_count[0] += 1

    if fix_type not in FIX_NAMES:
        logger.warning(f"{format_timestamp()} [WARN] unexpected fixType={fix_type}")
        warn_count[0] += 1

    return int(num_sv)


def handle_nav_satellites(msg: UBXMessage, logger: logging.Logger, warn_count: list) -> None:
    satellite_count = msg.numSvs
    parts = []
    for i in range(1, satellite_count + 1):
        gnss_id = getattr(msg, f"gnssId_{i:02d}", None)
        sv_id = getattr(msg, f"svId_{i:02d}", None)
        cno = getattr(msg, f"cno_{i:02d}", None)
        elev = getattr(msg, f"elev_{i:02d}", None)
        sv_used = bool(getattr(msg, f"svUsed_{i:02d}", 0))
        health = getattr(msg, f"health_{i:02d}", 0)

        if gnss_id is None:
            continue

        gnss_name = GNSS_NAMES.get(gnss_id, f"G{gnss_id}")
        used_marker = "*" if sv_used else " "
        health_str = "" if health == SatHealth.HEALTHY else f"[hlth={health}]"
        parts.append(f"{used_marker}{gnss_name}{sv_id} CN0={cno} el={elev}{health_str}")

        if sv_used and cno is not None and cno < WARN_CN0_MIN:
            logger.warning(
                f"{format_timestamp()} [WARN] {gnss_name}{sv_id} CN0={cno} dBHz below threshold ({WARN_CN0_MIN})"
            )
            warn_count[0] += 1

        if health == SatHealth.UNHEALTHY:
            logger.warning(f"{format_timestamp()} [WARN] {gnss_name}{sv_id} satellite is unhealthy")
            warn_count[0] += 1

    logger.info(f"{format_timestamp()} NAV-SAT  {satellite_count} svs  | {' | '.join(parts)}")


def handle_monitor_rf(msg: UBXMessage, logger: logging.Logger, warn_count: list) -> None:
    n_blocks = msg.nBlocks
    parts = []
    for i in range(1, n_blocks + 1):
        ant_status: int | None = getattr(msg, f"antStatus_{i:02d}", None)
        ant_power: int | None = getattr(msg, f"antPower_{i:02d}", None)
        jam_ind = getattr(msg, f"jamInd_{i:02d}", None)
        agc_cnt = getattr(msg, f"agcCnt_{i:02d}", None)
        noise = getattr(msg, f"noisePerMS_{i:02d}", None)
        jam_state = getattr(msg, f"jammingState_{i:02d}", 0)

        ant_str = ANT_STATUS.get(ant_status, f"?{ant_status}") if ant_status is not None else "?"
        pwr_str = ANT_POWER.get(ant_power, f"?{ant_power}") if ant_power is not None else "?"
        jam_state_str = JAM_STATE.get(jam_state, f"?{jam_state}")
        parts.append(f"ant={ant_str} pwr={pwr_str} jam={jam_ind}/255 state={jam_state_str} agc={agc_cnt} noise={noise}")

        if ant_status in (3, 4):  # SHORT or OPEN
            logger.warning(f"{format_timestamp()} [WARN] Antenna status: {ant_str}")
            warn_count[0] += 1

        if jam_ind is not None and jam_ind > WARN_JAM_MAX:
            logger.warning(f"{format_timestamp()} [WARN] Jamming indicator high: {jam_ind}/255")
            warn_count[0] += 1

        if jam_state in (2, 3):  # warning or critical
            logger.warning(f"{format_timestamp()} [WARN] Jamming state: {jam_state_str}")
            warn_count[0] += 1

    logger.info(f"{format_timestamp()} MON-RF   {' | '.join(parts)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="GPS debug script - NAV-PVT + NAV-SAT + MON-RF")
    parser.add_argument("--path", default=GPS_PATH, help="Serial port path (default: /dev/serial0)")
    args = parser.parse_args()

    logger = logging.getLogger("gps_debug")
    logger.info(f"Opening {args.path}...")

    warn_count = [0]
    prev_sats = None

    try:
        port = open_port(args.path, logger)
    except serial.SerialException as e:
        logger.error(f"Failed to open port: {e}")
        sys.exit(1)

    running = True

    def stop(_sig: int, _frame: types.FrameType | None) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    reader = UBXReader(port, quitonerror=ERR_IGNORE)
    logger.info("Waiting for messages... (Ctrl-C to stop)")
    logger.info("-" * 80)

    while running:
        try:
            _, msg = reader.read()
        except serial.SerialException as e:
            logger.error(f"Serial port error: {e}")
            break

        if msg is None:
            continue

        match msg.identity:
            case UBXMessageId.NAV_PVT:
                prev_sats = handle_nav_position_velocity_time(msg, prev_sats, logger, warn_count)
            case UBXMessageId.NAV_SAT:
                handle_nav_satellites(msg, logger, warn_count)
            case UBXMessageId.MON_RF:
                handle_monitor_rf(msg, logger, warn_count)
            case identity if identity.startswith(UBXMessageId.INF_PREFIX):
                logger.info(f"{format_timestamp()} {identity}: {getattr(msg, 'msgContent', identity)}")

    logger.info("-" * 80)
    if warn_count[0] > 0:
        logger.warning(f"Stopped. Total warnings: {warn_count[0]}")


if __name__ == "__main__":
    main()
