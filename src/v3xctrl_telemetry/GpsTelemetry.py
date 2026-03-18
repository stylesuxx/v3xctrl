from dataclasses import dataclass
import logging
import serial
from pyubx2 import POLL_LAYER_RAM, SET_LAYER_FLASH, TXN_NONE, UBXMessage, UBXReader

_POLL_BAUDRATES = (9600, 115200)
_ACK_READ_ATTEMPTS = 10
_SERIAL_TIMEOUT = 0.1

_DESIRED_CONFIG: dict[str, int] = {
    "CFG_UART1OUTPROT_UBX": 1,
    "CFG_UART1OUTPROT_NMEA": 0,
    "CFG_MSGOUT_UBX_NAV_PVT_UART1": 1,
    "CFG_RATE_MEAS": 1000,
}


@dataclass
class GpsState:
    lat: float = 0.0
    lng: float = 0.0
    fix: bool = False
    fix_type: int = 0  # 0=no fix, 1=dead reckoning, 2=2D, 3=3D, 4=GNSS+DR
    speed: float = 0.0  # km/h
    sats: int = 0


class GpsTelemetry:
    def __init__(self, path: str = "/dev/serial0") -> None:
        self._path = path
        self._state = GpsState()
        self._serial = self._configure_module()
        self._reader = UBXReader(self._serial)

    def update(self) -> bool:
        updated = False
        while self._serial.in_waiting:
            _, msg = self._reader.read()
            if msg is None:
                continue
            if msg.identity == "NAV-PVT":
                self._state.sats = msg.numSV
                self._state.fix_type = msg.fixType
                if msg.fixType >= 2:
                    self._state.lat = msg.lat
                    self._state.lng = msg.lon
                    self._state.speed = msg.gSpeed * 3.6 / 1000.0
                    self._state.fix = True
                else:
                    self._state.fix = False
                updated = True
        return updated

    def get_state(self) -> GpsState:
        return self._state

    def _open_and_poll(self, baudrate: int) -> tuple[serial.Serial, object] | None:
        logging.debug("GPS: probing config at %d baud on %s", baudrate, self._path)
        port = serial.Serial(self._path, baudrate, timeout=_SERIAL_TIMEOUT)
        try:
            port.reset_input_buffer()
            poll = UBXMessage.config_poll(POLL_LAYER_RAM, 0, list(_DESIRED_CONFIG.keys()))
            port.write(poll.serialize())
            port.flush()

            reader = UBXReader(port)
            for _ in range(_ACK_READ_ATTEMPTS):
                _, msg = reader.read()
                if msg is None:
                    continue
                if msg.identity == "CFG-VALGET":
                    logging.debug("GPS: received CFG-VALGET at %d baud", baudrate)
                    return port, msg
        except Exception as e:
            logging.debug("GPS: no response at %d baud: %s", baudrate, e)

        port.close()
        return None

    def _needs_update(self, msg: object) -> dict[str, tuple]:
        mismatches = {}
        for key, desired in _DESIRED_CONFIG.items():
            try:
                current = getattr(msg, key)
                if current != desired:
                    mismatches[key] = (current, desired)
            except AttributeError:
                logging.warning("GPS: CFG-VALGET response missing key %s, treating as mismatch", key)
                mismatches[key] = (None, desired)
        return mismatches

    def _write_flash_config(self, port: serial.Serial) -> bool:
        cfg = UBXMessage.config_set(SET_LAYER_FLASH, TXN_NONE, list(_DESIRED_CONFIG.items()))
        port.write(cfg.serialize())
        port.flush()

        reader = UBXReader(port)
        for _ in range(_ACK_READ_ATTEMPTS):
            _, msg = reader.read()
            if msg is None:
                continue
            if msg.identity == "ACK-ACK":
                logging.info("GPS: flash config written successfully on %s", self._path)
                return True
            if msg.identity == "ACK-NAK":
                logging.warning("GPS: flash write rejected (ACK-NAK) on %s", self._path)
                return False

        logging.warning("GPS: flash write no ACK received on %s", self._path)
        return False

    def _configure_module(self) -> serial.Serial:
        for baudrate in _POLL_BAUDRATES:
            result = self._open_and_poll(baudrate)
            if result is None:
                continue

            port, valget_msg = result
            mismatches = self._needs_update(valget_msg)

            if not mismatches:
                logging.info("GPS: flash config verified, no write needed (baud=%d)", baudrate)
                return port

            logging.info("GPS: config mismatch %s, writing to flash", list(mismatches.keys()))
            self._write_flash_config(port)
            return port

        logging.warning("GPS: config verification failed on %s, opening at 9600 without write", self._path)
        return serial.Serial(self._path, _POLL_BAUDRATES[0], timeout=_SERIAL_TIMEOUT)
