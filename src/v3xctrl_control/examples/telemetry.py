import time

from v3xctrl_control.Telemetry import Telemetry


telemetry = Telemetry('/dev/ttyACM0')
telemetry.start()

while True:
    print(telemetry.get_telemetry())
    time.sleep(1)

telemetry.stop()
telemetry.join()
