from v3xctrl_telemetry.INA import INA

address = 0x40
bus = 1

ina = INA(address, bus, r_shunt_ohms=0.005, max_expected_current_A=16)  # 5mΩ shunt, up to 16A

print("Bus Voltage:", ina.get_bus_voltage(), "mV")
print("Shunt Voltage:", ina.get_shunt_voltage(), "uV")
print("Current:", ina.get_current() / 1000, "mA")
print("Power:", ina.get_power() / 1000, "mW")
