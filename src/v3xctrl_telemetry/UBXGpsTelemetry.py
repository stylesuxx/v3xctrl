import logging
import time

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

from v3xctrl_telemetry.GpsTelemetry import GpsTelemetry

_POLL_BAUDRATES = (115200, 9600)
_BAUD_DETECT_TIMEOUT_S = 1.5   # per baud: raw read to detect \xb5\x62 sync; must exceed 1Hz message period
_CONFIG_POLL_TIMEOUT_S = 2.0   # wait for CFG-VALGET after poll
_ACK_READ_ATTEMPTS = 10        # attempts to read ACK after config write
_SERIAL_TIMEOUT = 0.1          # per-read timeout for steady-state update()

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
            if msg.identity.startswith("INF-"):
                logging.warning("GPS: module message: %s", getattr(msg, "msgContent", msg.identity))
            if msg.identity == "NAV-PVT":
                self._state.sats = msg.numSV
                self._state.fix_type = msg.fixType
                if msg.fixType >= 2:
                    self._state.lat = msg.lat
                    self._state.lng = msg.lon
                    self._state.speed = msg.gSpeed * 3.6 / 1000.0
                updated = True
        return updated

    def _open_at_baud(self, baudrate: int) -> serial.Serial | None:
        """Open port and confirm UBX data is present at this baud rate via raw byte check."""
        logging.debug("GPS: detecting baud at %d on %s", baudrate, self._path)
        port = serial.Serial(self._path, baudrate, timeout=_BAUD_DETECT_TIMEOUT_S)
        try:
            port.reset_input_buffer()
            raw = port.read(256)
            if b"\xb5\x62" in raw:
                logging.debug("GPS: UBX sync found at %d baud", baudrate)
                return port
            logging.debug("GPS: no UBX sync at %d baud", baudrate)
        except Exception as e:
            logging.debug("GPS: error detecting baud at %d: %s", baudrate, e)
        port.close()
        return None

    def _poll_config(self, port: serial.Serial, baudrate: int) -> object | None:
        """Send CFG-VALGET poll and return the response, or None if not received."""
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
                if msg.identity == "CFG-VALGET":
                    logging.debug("GPS: received CFG-VALGET at %d baud", baudrate)
                    return msg
                logging.debug("GPS: ignoring %s during config poll", msg.identity)
        except Exception as e:
            logging.debug("GPS: config poll error at %d baud: %s", baudrate, e)
        return None

    def _needs_update(self, msg: object) -> dict[str, tuple]:
        mismatches = {}
        for key, desired in self._desired_config.items():
            try:
                current = getattr(msg, key)
                if current != desired:
                    mismatches[key] = (current, desired)
            except AttributeError:
                logging.warning("GPS: CFG-VALGET response missing key %s, treating as mismatch", key)
                mismatches[key] = (None, desired)
        return mismatches

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
            if msg.identity == "ACK-ACK":
                logging.info("GPS: config written successfully on %s", self._path)
                return True
            if msg.identity == "ACK-NAK":
                logging.warning("GPS: config write rejected (ACK-NAK) on %s", self._path)
                return False

        logging.warning("GPS: config write no ACK received on %s", self._path)
        return False

    def _configure_module(self) -> serial.Serial:
        for baudrate in _POLL_BAUDRATES:
            port = self._open_at_baud(baudrate)
            if port is None:
                continue

            valget_msg = self._poll_config(port, baudrate)
            if valget_msg is None:
                logging.warning("GPS: baud detected at %d but no CFG-VALGET, using without config write", baudrate)
                return port

            mismatches = self._needs_update(valget_msg)
            if not mismatches:
                logging.info("GPS: config verified, no write needed (baud=%d)", baudrate)
                return port

            logging.info("GPS: config mismatch %s, writing to flash", list(mismatches.keys()))
            self._write_config(port)
            return port

        logging.warning("GPS: no UBX data on %s, opening at 9600 without config write", self._path)
        return serial.Serial(self._path, _POLL_BAUDRATES[-1], timeout=_SERIAL_TIMEOUT)
