# Hardware
This is a list of tested and recommended Hardware. Recommended in this case means, that it has been tested by the devs and works well (presumably out of the box). This is not a complete list of all compatible Hardware, but if you are running into issues, consider using something that has been extensively tested.

## Recommended
* [Raspberry PI Zero 2 W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/)
* [Cat 1, 4G Modem hat (comes in EU and US versions, with and without GPS)](https://aliexpress.com/item/1005007960858994.html)

## Potential candidates
* As 4G modem you could basically use anything that provides a RNDIS interface. Best option is something that also provides a serial interface to communicate with the modem to get signal quality information. This is not mandatory, but makes debugging easier.

* Any multi-core RPi (or alternative) with at least 512MB should be fine here. We rely on a hardware encoder for h264 encoding.

* [Cat 4, 4G Modem hat with GPS (SIM7600G-H 4G HAT)](https://aliexpress.com/item/1005005628834373.html)
