from dataclasses import dataclass
import logging
import time
import serial
from pyubx2 import SET_LAYER_FLASH, SET_LAYER_RAM, TXN_NONE, UBXMessage, UBXReader

_INITIAL_BAUDRATE = 9600
_CONFIG_DELAY = 0.1


@dataclass
class GpsState:
    lat: float = 0.0
    lng: float = 0.0
    fix: bool = False
    speed: float = 0.0  # km/h
    sats: int = 0


class GpsTelemetry:
    def __init__(self, path: str = "/dev/serial0", baudrate: int = 115200) -> None:
        self._path = path
        self._baudrate = baudrate
        self._state = GpsState()
        self._serial = self._configure_module()
        self._reader = UBXReader(self._serial)

    def update(self) -> None:
        _, msg = self._reader.read()
        if msg is None:
            return
        if msg.identity == "NAV-PVT":
            self._state.sats = msg.numSV
            if msg.fixType >= 2:
                self._state.lat = msg.lat
                self._state.lng = msg.lon
                self._state.speed = msg.gSpeed * 3.6 / 1000.0
                self._state.fix = True
            else:
                self._state.fix = False

    def get_state(self) -> GpsState:
        return self._state

    def _configure_module(self) -> serial.Serial:
        port = serial.Serial(self._path, _INITIAL_BAUDRATE, timeout=1.0)
        try:
            cfg = UBXMessage.config_set(
                SET_LAYER_RAM | SET_LAYER_FLASH,
                TXN_NONE,
                [
                    ("CFG_UART1_BAUDRATE", self._baudrate),
                    ("CFG_UART1OUTPROT_UBX", 1),
                    ("CFG_UART1OUTPROT_NMEA", 0),
                    ("CFG_MSGOUT_UBX_NAV_PVT_UART1", 1),
                ],
            )
            port.write(cfg.serialize())
            time.sleep(_CONFIG_DELAY)
        finally:
            port.close()

        logging.info("GPS configured at %d baud on %s", self._baudrate, self._path)
        return serial.Serial(self._path, self._baudrate, timeout=1.0)
