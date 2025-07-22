from smbus3 import SMBus
import time

# Default address - can be verified with: sudo i2cdetect -y 1
I2C_ADDR = 0x40

REG_BUS_VOLTAGE = 0x02
REG_SHUNT_VOLTAGE = 0x01
REG_CURRENT = 0x04
REG_CALIBRATION = 0x05

CALIBRATION_VALUE = 0x1000

BUS_VOLTAGE_UNIT = 1.25


def read_word(bus, addr, reg):
    raw = bus.read_word_data(addr, reg)
    # INA231 returns big-endian, swap bytes
    return ((raw << 8) & 0xFF00) | (raw >> 8)


with SMBus(1) as bus:
    # Write calibration register (mandatory to read current/power)
    calib = ((CALIBRATION_VALUE >> 8) & 0xFF, CALIBRATION_VALUE & 0xFF)
    bus.write_i2c_block_data(I2C_ADDR, REG_CALIBRATION, list(calib))

    time.sleep(0.01)

    bus_voltage_raw = read_word(bus, I2C_ADDR, REG_BUS_VOLTAGE)
    shunt_voltage_raw = read_word(bus, I2C_ADDR, REG_SHUNT_VOLTAGE)
    current_raw = read_word(bus, I2C_ADDR, REG_CURRENT)

    bus_voltage = bus_voltage_raw * BUS_VOLTAGE_UNIT  # in mV
    shunt_voltage = shunt_voltage_raw * 2.5  # in μV
    current = current_raw * 0.001  # depends on CALIBRATION

    print(f"Bus Voltage: {bus_voltage:.2f} mV")
    print(f"Shunt Voltage: {shunt_voltage:.2f} µV")
    print(f"Current (raw): {current_raw} → {current:.3f} mA (scale depends on calibration)")
