from v3xctrl_telemetry import Battery
import time

min_voltage = 3.5 * 1000
max_voltage = 4.2 * 1000
warn_voltage = 3.7 * 1000

battery = Battery(min_voltage, max_voltage, warn_voltage)

while True:
    battery.update()
    print("Voltage:", battery.get_volts())
    print("Average:", battery.average_voltage)
    print(battery.voltage, "mV")
    print(battery.percentage, "%")
    print("Cells:", battery.cell_count)
    print("Warning:", battery.warning)

    time.sleep(1)
