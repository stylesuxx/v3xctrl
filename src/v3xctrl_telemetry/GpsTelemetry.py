from dataclasses import dataclass
import logging
import time
import serial
from pyubx2 import UBXMessage, UBXReader, SET


# UBX-CFG-VALSET key IDs for M10 UART1 configuration
_CFG_UART1_BAUDRATE = "CFG_UART1_BAUDRATE"
_CFG_UART1OUTPROT_UBX = "CFG_UART1OUTPROT_UBX"
_CFG_UART1OUTPROT_NMEA = "CFG_UART1OUTPROT_NMEA"
_CFG_MSGOUT_UBX_NAV_PVT_UART1 = "CFG_MSGOUT_UBX_NAV_PVT_UART1"

_INITIAL_BAUDRATE = 9600
_CONFIG_DELAY = 0.1


@dataclass
class GpsState:
    lat: float = 0.0
    lng: float = 0.0
    fix: bool = False


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
        if msg.identity == "NAV-PVT" and msg.fixType >= 2:
            self._state.lat = msg.lat
            self._state.lng = msg.lon
            self._state.fix = True

    def get_state(self) -> GpsState:
        return self._state

    def _configure_module(self) -> serial.Serial:
        port = serial.Serial(self._path, _INITIAL_BAUDRATE, timeout=1.0)
        try:
            cfg = UBXMessage(
                "CFG",
                "CFG-VALSET",
                SET,
                transaction=0,
                layers=1,
                **{
                    _CFG_UART1_BAUDRATE: self._baudrate,
                    _CFG_UART1OUTPROT_UBX: 1,
                    _CFG_UART1OUTPROT_NMEA: 0,
                    _CFG_MSGOUT_UBX_NAV_PVT_UART1: 1,
                }
            )
            port.write(cfg.serialize())
            time.sleep(_CONFIG_DELAY)
        finally:
            port.close()

        logging.info("GPS configured at %d baud on %s", self._baudrate, self._path)
        return serial.Serial(self._path, self._baudrate, timeout=1.0)
