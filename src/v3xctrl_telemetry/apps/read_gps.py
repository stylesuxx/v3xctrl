from v3xctrl_telemetry.GpsTelemetry import GpsTelemetry

gps = GpsTelemetry()

print("Waiting for NAV-PVT messages... (Ctrl-C to stop)")
while True:
    gps.update()
    state = gps.get_state()
    print(state)
