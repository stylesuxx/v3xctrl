from v3xctrl_telemetry import GstTelemetry

telemetry = GstTelemetry()
telemetry.update()

stats = telemetry.stats()

print(stats)
