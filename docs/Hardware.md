# Hardware

This is a list of tested and recommended Hardware. **Recommended** means it has been tested by the developers and works well (presumably out of the box). This is not a complete list of all compatible Hardware, but if you run into issues, consider using something that has been extensively tested.

## Recommended

* [Raspberry PI Zero 2 W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/)
* [Cat 1, 4G Modem hat (comes in EU and US versions, with and without GPS)](https://aliexpress.com/item/1005007960858994.html) - Explicitly tested firmware versions: `AirM2M_780EU_V1138_LTE_AT`
* [PiCam V3 (Wide) - only cam so far with HDR](https://www.raspberrypi.com/products/camera-module-3/)


## Tested

### Modems

* [Cat 1, 4G Modem hat with GPS (Variant: Zero-4G-CAT1-GPS)](https://de.aliexpress.com/item/1005007960858994.html) - Default frequency bands are set for the Chinese (Asian) market: `1, 3, 8, 34, 38, 39, 40, 41`

## Potential Candidates

The following components are expected to work but have not been explicitly tested.

### SBC

* Any multi-core Raspberry Pi (or alternative SBC) with at least 512MB of RAM should be sufficient. A hardware encoder for H.264 is required.

### Modems

* Any 4G modem that provides an **RNDIS interface** should work.

> It is strongly recommended to use a modem that also provides a **serial interface** for querying modem stats via AT commands. Without this, features like reception monitoring, signal quality reporting, and band limitation configuration will not work.

* [Cat 4, 4G Modem hat with GPS (SIM7600G-H 4G HAT)](https://aliexpress.com/item/1005005628834373.html)

### Cameras

Technically, any compatible camera should work. However, we recommend the [PiCam V3 (Wide version)](https://www.raspberrypi.com/products/camera-module-3/) as it is currently the only camera that supports HDR, which helps with difficult lighting conditions.

If HDR is not important for your setup, any PiCam, ArduCam, or compatible clone should work. We recommend choosing one with a decent FOV (Field of View).
