from dataclasses import dataclass
import logging
import time
import serial
from pyubx2 import SET_LAYER_RAM, TXN_NONE, UBXMessage, UBXReader

_INITIAL_BAUDRATE = 9600
_CONFIG_DELAY = 0.5


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

    def _configure_module(self) -> serial.Serial:
        port = serial.Serial(self._path, _INITIAL_BAUDRATE, timeout=1.0)
        try:
            cfg = UBXMessage.config_set(
                SET_LAYER_RAM,
                TXN_NONE,
                [
                    ("CFG_UART1OUTPROT_UBX", 1),
                    ("CFG_UART1OUTPROT_NMEA", 0),
                    ("CFG_MSGOUT_UBX_NAV_PVT_UART1", 1),
                    ("CFG_RATE_MEAS", 1000),
                ],
            )
            port.write(cfg.serialize())
            port.flush()

            reader = UBXReader(port)
            for _ in range(10):
                _, msg = reader.read()
                if msg is None:
                    continue
                if msg.identity == "ACK-ACK":
                    logging.info("GPS configured successfully on %s", self._path)
                    return port
                if msg.identity == "ACK-NAK":
                    logging.warning("GPS configuration rejected (ACK-NAK) on %s", self._path)
                    return port
        except Exception as e:
            logging.warning("GPS configuration error: %s", e)

        logging.warning("GPS configuration: no ACK received on %s", self._path)
        return port
