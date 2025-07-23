# Hardware
This is a list of tested and recommended Hardware. Recommended in this case means, that it has been tested by the devs and works well (presumably out of the box). This is not a complete list of all compatible Hardware, but if you are running into issues, consider using something that has been extensively tested.

## Recommended
* [Raspberry PI Zero 2 W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/)
* [Cat 1, 4G Modem hat (comes in EU and US versions, with and without GPS)](https://aliexpress.com/item/1005007960858994.html) - Explicitly tested firmware versions: `AirM2M_780EU_V1138_LTE_AT`
* [PiCam V3 (Wide) - only cam so far with HDR](https://www.raspberrypi.com/products/camera-module-3/)
* [INA231]() - smallest breakout board for the INA current/voltage sensor

## Tested

### Modems
* [Cat 1, 4G Modem hat with GPS (Variant: Zero-4G-CAT1-GPS)](https://de.aliexpress.com/item/1005007960858994.html) - the default bands are for the Chinese (Asian) Market: `1, 3, 8, 38, 39, 40, 41` but they can be changed according to your region.

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



## AT command cheat sheet
When evaluating new modems the following AT commands can be useful:

> For more complex operations use [python ATlib](https://pypi.org/project/atlib).

### AT+VER
Get firmware version:

```
AT+VER?
```

### AT+CREG?
Shows if modem is registered with network.

```
# Not connected
+CREG: 0,0

# Connected
+CREG: 0,1
```

### AT*BANDIND?
Shows currently used band:

```
*BANDIND: 0, 3, 7
```

The middle number is the band, so band **3** in this case.
