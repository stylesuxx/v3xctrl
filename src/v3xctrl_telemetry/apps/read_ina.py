from v3xctrl_telemetry import INA

address = 0x40
bus = 1

ina = INA(address, bus)

print("Bus Voltage:", ina.get_bus_voltage(), "mV")
print("Shunt Voltage:", ina.get_shunt_voltage(), "uV")
print("Current:", ina.get_current(), "uA")
print("Power:", ina.get_power(), "uW")
