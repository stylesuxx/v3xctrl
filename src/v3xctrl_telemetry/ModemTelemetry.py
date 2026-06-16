"""
Modem telemetry source.

Wraps AT-based signal/cell queries against an Air780EU modem. One `update()`
call performs a single AT session that produces both signal quality and cell
location, returned together as a `ModemState`.

Init failures, missing SIM, and per-update exceptions are absorbed: `update()`
never raises. If the modem becomes unreachable we drop back to "unknown"
state values and periodically retry the init (mirrors the previous behavior
inside `v3xctrl_control/Telemetry.py`).
"""

import logging

from atlib import AIR780EU

from v3xctrl_telemetry.dataclasses import ModemState

logger = logging.getLogger(__name__)


class ModemTelemetry:
    SIM_RECHECK_INTERVAL = 30

    def __init__(self, modem_path: str) -> None:
        self._modem_path = modem_path
        self._modem: AIR780EU | None = None
        self._init_failed = False
        self._sim_absent = False
        self._sim_recheck_counter = 0
        self._state = ModemState()
        self._init_modem()

    def update(self) -> None:
        if not self._modem_available():
            self._reset_state()
            return

        modem = self._modem
        assert modem is not None  # _modem_available guarantees this

        try:
            signal_quality = modem.get_signal_quality()
            band = modem.get_active_band()
            cell_id = modem.get_cell_location()[3]

        except Exception as exc:
            logger.debug("Failed to read modem telemetry: %s", exc)
            self._modem = None
            self._reset_state()
            return

        self._state = ModemState(
            rsrq=signal_quality.rsrq,
            rsrp=signal_quality.rsrp,
            cell_id=cell_id,
            band=band,
        )

    def get_state(self) -> ModemState:
        return self._state

    def _reset_state(self) -> None:
        self._state = ModemState()

    def _modem_available(self) -> bool:
        if self._modem:
            return True

        if self._sim_absent:
            self._sim_recheck_counter += 1
            if self._sim_recheck_counter < self.SIM_RECHECK_INTERVAL:
                return False
            self._sim_recheck_counter = 0

        return self._init_modem()

    def _init_modem(self) -> bool:
        try:
            modem = AIR780EU(self._modem_path)
            modem.enable_location_reporting()

            sim_status = modem.get_sim_status()
            if sim_status != "OK":
                logger.info("No SIM card present (status: %s)", sim_status)
                self._modem = None
                self._sim_absent = True
                return False

            self._modem = modem
            self._sim_absent = False
            if self._init_failed:
                logger.info("Modem recovered")

            self._init_failed = False
            logger.info("Modem initialized")

            return True

        except Exception as exc:
            if not self._init_failed:
                logger.warning("Failed to initialize modem: %s", exc)
                self._init_failed = True
            self._modem = None

            return False
