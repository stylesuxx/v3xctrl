# Pinout
Connect your periperals according to the following pinout:

| GPIO | Protocol | Function |
|------|----------|----------|
| 3 | I2C | SDA |
| 5 | I2C | SCL |
| 13| PWM | Servo |
| 18| PWM | Speed-controller |

> Some pins might be configurable, but wiring up like this will be the easiest, most consistent and reliable way.

## INAxxx - current/voltage sensor

> Make sure you power your INAxxx from 3.3V! It will not work with 5V and you are running risk of damaging the sensor.

Voltage is measured via bus pin, not the main pins over the shunt - those are only used for current sensing (which is not yet implemented).
