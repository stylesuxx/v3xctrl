import logging
import time

from v3xctrl_telemetry.UBXGpsTelemetry import UBXGpsTelemetry

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

gps = UBXGpsTelemetry()

logger.info("Waiting for NAV-PVT messages... (Ctrl-C to stop)")
last_time = None
last_fix_type = None
while True:
    if gps.update():
        now = time.time()
        state = gps.get_state()
        fix = gps.get_fix()

        interval = f"{(now - last_time) * 1000:.0f}ms" if last_time is not None else "---"
        last_time = now

        fix_changed = last_fix_type is not None and state.fix_type != last_fix_type
        last_fix_type = state.fix_type

        marker = " <<< FIX CHANGED" if fix_changed else ""
        stamp = f"{time.strftime('%H:%M:%S')}.{int(now % 1 * 1000):03d}"
        logger.info("[%s] (+%s) %s%s", stamp, interval, state, marker)

        if fix is not None:
            logger.info(
                "    alt=%.1fm head=%.1f° hAcc=%.1fm pDOP=%.2f fixOk=%s posValid=%s",
                fix.altitude,
                fix.heading,
                fix.horizontal_accuracy,
                fix.pdop,
                fix.fix_ok,
                fix.position_valid,
            )
