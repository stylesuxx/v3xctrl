from v3xctrl_telemetry.BatteryTelemetry import BatteryTelemetry

min_voltage = int(3.5 * 1000)
max_voltage = int(4.2 * 1000)
warn_voltage = int(3.7 * 1000)

battery = BatteryTelemetry(min_voltage, max_voltage, warn_voltage)
battery.update()

state = battery.get_state()
print(state)
