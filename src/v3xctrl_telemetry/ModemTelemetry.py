"""
Modem telemetry source.

Wraps AT-based signal/cell queries against an Air780EU modem. One `update()` call
performs a single AT session that produces both signal quality and cell location,
returned together as a `ModemState`.

A modem that cannot be reached at all raises from the constructor, leaving the collector
to retry. A modem that answers but holds no SIM is a working device: it keeps its serial
session and rechecks for a card every `SIM_RECHECK_INTERVAL_S`, reporting an empty state
in the meantime.
"""

import logging
import time

from atlib import AIR780EU

from v3xctrl_telemetry.dataclasses import ModemState

logger = logging.getLogger(__name__)


class ModemTelemetry:
    SIM_RECHECK_INTERVAL_S = 30.0

    def __init__(self, modem_path: str) -> None:
        self._modem = AIR780EU(modem_path)
        self._modem.enable_location_reporting()

        self._state = ModemState()
        self._is_sim_absent = False
        self._sim_recheck_deadline = 0.0
        self._check_sim()

    def update(self) -> None:
        if self._is_sim_absent:
            if time.monotonic() < self._sim_recheck_deadline:
                return

            self._check_sim()
            if self._is_sim_absent:
                return

        signal_quality = self._modem.get_signal_quality()
        band = self._modem.get_active_band()
        cell_id = self._modem.get_cell_location()[3]

        self._state = ModemState(
            rsrq=signal_quality.rsrq,
            rsrp=signal_quality.rsrp,
            cell_id=cell_id,
            band=band,
        )

    def get_state(self) -> ModemState:
        return self._state

    def _check_sim(self) -> None:
        sim_status = self._modem.get_sim_status()
        self._sim_recheck_deadline = time.monotonic() + self.SIM_RECHECK_INTERVAL_S

        was_absent = self._is_sim_absent
        self._is_sim_absent = sim_status != "OK"

        if self._is_sim_absent:
            self._state = ModemState()
            if not was_absent:
                logger.info("No SIM card present (status: %s)", sim_status)

        elif was_absent:
            logger.info("SIM card present")
