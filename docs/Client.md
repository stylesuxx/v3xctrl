# Client
There are multiple hardware platforms that can be used as clients. We decided to go with a 'Raspberry Pi Zero 2 W' for this project.

The 'Raspberry Pi Zero 2 W' has most of what we need:
* small size
* widely available
* hardware video encoder
* dedicated camera platform
* USB
* Wifi
* GPIO

The 'RPi Zero 2 W' has no issues encoding video streams in realtime in 1920x1080@30fps. This will only be feasible with higher category 4G modems but obviously lower resolution won't be an issue either.

## Hardware
The client will be interacting with different sensor and actuators. This is a selection of some useful things to consider:

Sensors:
* INA219 for measuring battery voltage
* GPS ()

Actuators:
* Speedcontroller (PWM based) - preferably with BEC to supply Servo(s) with power
* Servo(s) (PWM based)

Power supply:
* Step down converter to provide stable 5V@3A

Modem:
* 4G Modem - as long as it provides a rndis device, any is fine - as mentioned above, higher category is preferred.

## Software
As base we decided to use PiOS. Unfortunately, Bookworm seems to have some issues with the RNDIS modem, so we went with Bullseye.

But generally speaking, the exact distribution should not matter too much. We will be using Python for the client side.

In the packages file you can see a list of packages that I installed on PiOS Bullseye starting with the 'Lite' base image.
