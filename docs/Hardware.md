# Hardware
This is a list of tested and recommended Hardware. Recommended in this case means, that it has been tested by the devs and works well (presumably out of the box). This is not a complete list of all compatible Hardware, but if you are running into issues, consider using something that has been extensively tested.

## Recommended
* [Raspberry PI Zero 2 W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/)
* [Cat 1, 4G Modem hat (comes in EU and US versions, with and without GPS)](https://aliexpress.com/item/1005007960858994.html)
* [PiCam V3 (Wide)](https://www.raspberrypi.com/products/camera-module-3/)


## Tested

## Potential candidates

The following components are potential candidates that should work, but have not explicitly been tested.

### SBC
* Any multi-core RPi (or alternative) with at least 512MB should be fine here. We rely on a hardware encoder for h264 encoding.

### Modems
* As 4G modem you could basically use anything that provides a RNDIS interface.

> You should also really go with something that provides a serial interface to query Modem stats via AT commands - otherwise features like reception, signal quality and band limitations will not work.

* [Cat 4, 4G Modem hat with GPS (SIM7600G-H 4G HAT)](https://aliexpress.com/item/1005005628834373.html)

### Cameras
Technically any camera should work, but we recommend the [PiCam V3 (Wide version)](https://www.raspberrypi.com/products/camera-module-3/) as it is the only camera that supports HDR, which helps with difficult lighting conditions.

If you don't care for that, any PiCam, ArduCam and knockoffs are fine. Go for a decent FOV though.
