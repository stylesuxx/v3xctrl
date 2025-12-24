from v3xctrl_telemetry.GstTelemetry import GstTelemetry

telemetry = GstTelemetry()
telemetry.update()

stats = telemetry.get_state()
print(stats)
