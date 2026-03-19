import logging
import time
from enum import StrEnum

import serial
from pyubx2 import (
    ERR_IGNORE,
    POLL_LAYER_RAM,
    SET_LAYER_BBR,
    SET_LAYER_FLASH,
    SET_LAYER_RAM,
    TXN_NONE,
    UBXMessage,
    UBXReader,
)

from v3xctrl_telemetry.dataclasses import GpsFixType
from v3xctrl_telemetry.GpsTelemetry import GpsTelemetry

logger = logging.getLogger(__name__)

_POLL_BAUDRATES = (115200, 9600)
_BAUD_DETECT_TIMEOUT_S = 1.5  # per baud: raw read to detect \xb5\x62 sync; must exceed 1Hz message period
_CONFIG_POLL_TIMEOUT_S = 2.0  # wait for CFG-VALGET after poll
_ACK_READ_ATTEMPTS = 10  # attempts to read ACK after config write
_SERIAL_TIMEOUT = 0.1  # per-read timeout for steady-state update()


class UBXMessageId(StrEnum):
    NAV_PVT = "NAV-PVT"
    CFG_VALGET = "CFG-VALGET"
    ACK_ACK = "ACK-ACK"
    ACK_NAK = "ACK-NAK"
    INF_PREFIX = "INF-"


class UBXGpsTelemetry(GpsTelemetry):
    def __init__(self, path: str = "/dev/serial0", rate_hz: int = 5) -> None:
        super().__init__()
        self._path = path
        self._desired_config: dict[str, int] = {
            "CFG_UART1OUTPROT_UBX": 1,
            "CFG_UART1OUTPROT_NMEA": 0,
            "CFG_MSGOUT_UBX_NAV_PVT_UART1": 1,
            "CFG_RATE_MEAS": 1000 // rate_hz,
        }
        self._serial = self._configure_module()
        self._reader = UBXReader(self._serial)

    def update(self) -> bool:
        updated = False
        while self._serial.in_waiting:
            _, msg = self._reader.read()
            if msg is None:
                continue
            if msg.identity.startswith(UBXMessageId.INF_PREFIX):
                logger.warning("GPS: module message: %s", getattr(msg, "msgContent", msg.identity))
            if msg.identity == UBXMessageId.NAV_PVT:
                self._state.satellites = msg.numSV
                try:
                    self._state.fix_type = GpsFixType(msg.fixType)
                except ValueError:
                    self._state.fix_type = GpsFixType.NO_FIX
                if self._state.fix_type >= GpsFixType.FIX_2D:
                    self._state.lat = msg.lat
                    self._state.lng = msg.lon
                    self._state.speed = msg.gSpeed * 3.6 / 1000.0
                updated = True
        return updated

    def _open_at_baud(self, baudrate: int) -> serial.Serial | None:
        """Open port and confirm UBX data is present at this baud rate via raw byte check."""
        logger.debug("GPS: detecting baud at %d on %s", baudrate, self._path)
        port = serial.Serial(self._path, baudrate, timeout=_BAUD_DETECT_TIMEOUT_S)
        try:
            port.reset_input_buffer()
            raw = port.read(256)
            if b"\xb5\x62" in raw:
                logger.debug("GPS: UBX sync found at %d baud", baudrate)
                return port
            logger.debug("GPS: no UBX sync at %d baud", baudrate)
        except Exception as e:
            logger.debug("GPS: error detecting baud at %d: %s", baudrate, e)
        port.close()
        return None

    def _poll_config(self, port: serial.Serial, baudrate: int) -> dict[str, int] | None:
        """Send CFG-VALGET poll and return current config values as a dict, or None if not received."""
        try:
            port.reset_input_buffer()
            poll = UBXMessage.config_poll(POLL_LAYER_RAM, 0, list(self._desired_config.keys()))
            port.write(poll.serialize())
            port.flush()
            reader = UBXReader(port, quitonerror=ERR_IGNORE)
            deadline = time.monotonic() + _CONFIG_POLL_TIMEOUT_S
            while time.monotonic() < deadline:
                _, msg = reader.read()
                if msg is None:
                    continue
                if msg.identity == UBXMessageId.CFG_VALGET:
                    logger.debug("GPS: received CFG-VALGET at %d baud", baudrate)
                    config: dict[str, int] = {}
                    for key in self._desired_config:
                        value = getattr(msg, key, None)
                        if value is None:
                            logger.warning("GPS: CFG-VALGET response missing key %s", key)
                        else:
                            config[key] = value
                    return config
                logger.debug("GPS: ignoring %s during config poll", msg.identity)
        except Exception as e:
            logger.debug("GPS: config poll error at %d baud: %s", baudrate, e)
        return None

    def _needs_update(self, current_config: dict[str, int]) -> set[str]:
        return {key for key, desired in self._desired_config.items() if current_config.get(key) != desired}

    def _write_config(self, port: serial.Serial) -> bool:
        layers = SET_LAYER_RAM | SET_LAYER_BBR | SET_LAYER_FLASH
        cfg = UBXMessage.config_set(layers, TXN_NONE, list(self._desired_config.items()))
        port.write(cfg.serialize())
        port.flush()

        reader = UBXReader(port)
        for _ in range(_ACK_READ_ATTEMPTS):
            _, msg = reader.read()
            if msg is None:
                continue
            if msg.identity == UBXMessageId.ACK_ACK:
                logger.info("GPS: config written successfully on %s", self._path)
                return True
            if msg.identity == UBXMessageId.ACK_NAK:
                logger.warning("GPS: config write rejected (ACK-NAK) on %s", self._path)
                return False

        logger.warning("GPS: config write no ACK received on %s", self._path)
        return False

    def _configure_module(self) -> serial.Serial:
        for baudrate in _POLL_BAUDRATES:
            port = self._open_at_baud(baudrate)
            if port is None:
                continue

            current_config = self._poll_config(port, baudrate)
            if current_config is None:
                logger.warning("GPS: baud detected at %d but no CFG-VALGET, using without config write", baudrate)
                return port

            mismatches = self._needs_update(current_config)
            if not mismatches:
                logger.info("GPS: config verified, no write needed (baud=%d)", baudrate)
                return port

            logger.info("GPS: config mismatch %s, writing to flash", list(mismatches))
            self._write_config(port)
            return port

        logger.warning("GPS: no UBX data on %s, opening at 9600 without config write", self._path)
        return serial.Serial(self._path, _POLL_BAUDRATES[-1], timeout=_SERIAL_TIMEOUT)
