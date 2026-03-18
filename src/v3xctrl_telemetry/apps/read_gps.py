import logging
import time

from v3xctrl_telemetry.UBXGpsTelemetry import UBXGpsTelemetry

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")

gps = UBXGpsTelemetry()

print("Waiting for NAV-PVT messages... (Ctrl-C to stop)")
last_time = None
last_fix = None
while True:
    if gps.update():
        now = time.time()
        state = gps.get_state()

        interval = f"{(now - last_time) * 1000:.0f}ms" if last_time is not None else "---"
        last_time = now

        fix_changed = last_fix is not None and state.fix != last_fix
        last_fix = state.fix

        marker = " <<< FIX CHANGED" if fix_changed else ""
        print(f"[{time.strftime('%H:%M:%S')}.{int(now % 1 * 1000):03d}] (+{interval}) {state}{marker}")
