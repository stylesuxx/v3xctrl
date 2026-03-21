"""
GPS debug script - reads NAV-PVT, NAV-SAT, and MON-RF from a u-blox M10 module.

Enables additional diagnostic messages in RAM only (flash config is not modified).
Logs all output to /data/gps_debug_<timestamp>.log and prints to stdout.

Usage:
    python -m v3xctrl_telemetry.apps.debug_gps [--path /dev/serial0]

Press Ctrl-C to stop. A warning summary is printed on exit.
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import serial
from pyubx2 import ERR_IGNORE, SET_LAYER_RAM, TXN_NONE, UBXMessage, UBXReader

# --- Constants ---

GPS_PATH = "/dev/serial0"
POLL_BAUDRATES = (115200, 9600)
BAUD_DETECT_TIMEOUT_S = 1.5
SERIAL_TIMEOUT = 0.1

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

LOG_DIR = Path("/data")

WARN_CN0_MIN = 25  # dBHz - below this for a used satellite is poor signal
WARN_JAM_MAX = 50  # 0-255 - above this is a jamming concern
WARN_SAT_DROP = 2  # warn if numSV drops by this many or more in one cycle

GNSS_NAMES = {0: "GPS", 1: "SBAS", 2: "GAL", 3: "BDS", 4: "IMES", 5: "QZSS", 6: "GLO"}
ANT_STATUS = {0: "INIT", 1: "UNKN", 2: "OK", 3: "SHORT", 4: "OPEN"}
ANT_POWER = {0: "OFF", 1: "ON", 2: "UNKN"}
JAM_STATE = {0: "unknown", 1: "ok", 2: "WARNING", 3: "CRITICAL"}
FIX_NAMES = {0: "NO_FIX", 1: "DR", 2: "2D", 3: "3D", 4: "GNSS+DR", 5: "TIME_ONLY"}


# --- Logging setup ---


def setup_logging() -> tuple[logging.Logger, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if LOG_DIR.exists():
        log_file = LOG_DIR / f"gps_debug_{timestamp}.log"
    else:
        log_file = Path(f"gps_debug_{timestamp}.log")
        print(f"[WARN] /data not found, logging to {log_file.absolute()}")

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file),
        ],
    )
    return logging.getLogger("gps_debug"), log_file


def ts() -> str:
    now = time.time()
    return f"[{time.strftime('%H:%M:%S')}.{int(now % 1 * 1000):03d}]"


# --- Serial / config ---


def open_at_baud(path: str, baudrate: int) -> serial.Serial | None:
    port = serial.Serial(path, baudrate, timeout=BAUD_DETECT_TIMEOUT_S)
    try:
        port.reset_input_buffer()
        raw = port.read(256)
        if b"\xb5\x62" in raw:
            return port
    except Exception:
        pass
    port.close()
    return None


def apply_debug_config(port: serial.Serial, logger: logging.Logger) -> None:
    port.timeout = SERIAL_TIMEOUT
    cfg = UBXMessage.config_set(SET_LAYER_RAM, TXN_NONE, list(DEBUG_CONFIG.items()))
    port.write(cfg.serialize())
    port.flush()
    reader = UBXReader(port, quitonerror=ERR_IGNORE)
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        _, msg = reader.read()
        if msg is None:
            continue
        if msg.identity == "ACK-ACK":
            logger.info(f"{ts()} Config applied (RAM only - flash unchanged, reverts on power cycle)")
            return
        if msg.identity == "ACK-NAK":
            logger.warning(f"{ts()} [WARN] Module rejected debug config")
            return
    logger.warning(f"{ts()} [WARN] No ACK received for debug config write")


def open_port(path: str, logger: logging.Logger) -> serial.Serial:
    for baudrate in POLL_BAUDRATES:
        port = open_at_baud(path, baudrate)
        if port is not None:
            logger.info(f"{ts()} UBX sync found at {baudrate} baud on {path}")
            apply_debug_config(port, logger)
            return port
    logger.warning(f"{ts()} [WARN] No UBX sync found, opening at 9600 without config")
    return serial.Serial(path, POLL_BAUDRATES[-1], timeout=SERIAL_TIMEOUT)


# --- Message formatters ---


def handle_nav_pvt(msg, prev_sats: int | None, logger: logging.Logger, warn_count: list) -> int:
    fix_type = msg.fixType
    num_sv = msg.numSV
    fix_name = FIX_NAMES.get(fix_type, f"UNK({fix_type})")

    if fix_type >= 2:
        pos = f"lat={msg.lat:.6f}  lon={msg.lon:.6f}  speed={msg.gSpeed * 3.6 / 1000:.1f} km/h"
    else:
        pos = "lat=--  lon=--  speed=--"

    logger.info(f"{ts()} NAV-PVT  fix={fix_name}  sats={num_sv}  {pos}")

    if prev_sats is not None and (prev_sats - num_sv) >= WARN_SAT_DROP:
        logger.warning(f"{ts()} [WARN] sats dropped {prev_sats} -> {num_sv}")
        warn_count[0] += 1

    if fix_type not in FIX_NAMES:
        logger.warning(f"{ts()} [WARN] unexpected fixType={fix_type}")
        warn_count[0] += 1

    return num_sv


def handle_nav_sat(msg, logger: logging.Logger, warn_count: list) -> None:
    num_svs = msg.numSvs
    parts = []
    for i in range(1, num_svs + 1):
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
        health_str = "" if health == 1 else f"[hlth={health}]"
        parts.append(f"{used_marker}{gnss_name}{sv_id} CN0={cno} el={elev}{health_str}")

        if sv_used and cno is not None and cno < WARN_CN0_MIN:
            logger.warning(f"{ts()} [WARN] {gnss_name}{sv_id} CN0={cno} dBHz below threshold ({WARN_CN0_MIN})")
            warn_count[0] += 1

        if health == 2:
            logger.warning(f"{ts()} [WARN] {gnss_name}{sv_id} satellite is unhealthy")
            warn_count[0] += 1

    logger.info(f"{ts()} NAV-SAT  {num_svs} svs  | {' | '.join(parts)}")


def handle_mon_rf(msg, logger: logging.Logger, warn_count: list) -> None:
    n_blocks = msg.nBlocks
    parts = []
    for i in range(1, n_blocks + 1):
        ant_status = getattr(msg, f"antStatus_{i:02d}", None)
        ant_power = getattr(msg, f"antPower_{i:02d}", None)
        jam_ind = getattr(msg, f"jamInd_{i:02d}", None)
        agc_cnt = getattr(msg, f"agcCnt_{i:02d}", None)
        noise = getattr(msg, f"noisePerMS_{i:02d}", None)
        jam_state = getattr(msg, f"jammingState_{i:02d}", 0)

        ant_str = ANT_STATUS.get(ant_status, f"?{ant_status}")
        pwr_str = ANT_POWER.get(ant_power, f"?{ant_power}")
        jam_state_str = JAM_STATE.get(jam_state, f"?{jam_state}")
        parts.append(f"ant={ant_str} pwr={pwr_str} jam={jam_ind}/255 state={jam_state_str} agc={agc_cnt} noise={noise}")

        if ant_status in (3, 4):  # SHORT or OPEN
            logger.warning(f"{ts()} [WARN] Antenna status: {ant_str}")
            warn_count[0] += 1

        if jam_ind is not None and jam_ind > WARN_JAM_MAX:
            logger.warning(f"{ts()} [WARN] Jamming indicator high: {jam_ind}/255")
            warn_count[0] += 1

        if jam_state in (2, 3):  # warning or critical
            logger.warning(f"{ts()} [WARN] Jamming state: {jam_state_str}")
            warn_count[0] += 1

    logger.info(f"{ts()} MON-RF   {' | '.join(parts)}")


# --- Entry point ---


def main() -> None:
    parser = argparse.ArgumentParser(description="GPS debug script - NAV-PVT + NAV-SAT + MON-RF")
    parser.add_argument("--path", default=GPS_PATH, help="Serial port path (default: /dev/serial0)")
    args = parser.parse_args()

    logger, log_file = setup_logging()
    logger.info(f"Log: {log_file.absolute()}")
    logger.info(f"Opening {args.path}...")

    warn_count = [0]
    prev_sats = None

    try:
        port = open_port(args.path, logger)
    except Exception as e:
        logger.error(f"Failed to open port: {e}")
        sys.exit(1)

    reader = UBXReader(port, quitonerror=ERR_IGNORE)
    logger.info("Waiting for messages... (Ctrl-C to stop)")
    logger.info("-" * 80)

    try:
        while True:
            _, msg = reader.read()
            if msg is None:
                continue
            if msg.identity == "NAV-PVT":
                prev_sats = handle_nav_pvt(msg, prev_sats, logger, warn_count)
            elif msg.identity == "NAV-SAT":
                handle_nav_sat(msg, logger, warn_count)
            elif msg.identity == "MON-RF":
                handle_mon_rf(msg, logger, warn_count)
            elif msg.identity.startswith("INF-"):
                logger.info(f"{ts()} {msg.identity}: {getattr(msg, 'msgContent', msg.identity)}")
    except KeyboardInterrupt:
        logger.info("-" * 80)
        if warn_count[0] == 0:
            logger.info("Stopped. No warnings.")
        else:
            logger.warning(f"Stopped. Total warnings: {warn_count[0]}")


if __name__ == "__main__":
    main()
