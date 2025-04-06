# Hardware
This is a list of tested and recommended Hardware. Recommended in this case means, that it has been tested by the devs and works well (presumably out of the box). This is not a complete list of all compatible Hardware, but if you are running into issues, consider using something that has been extensively tested.

* [Raspberry PI Zero 2 W]()
* [4G Modem hat (comes in EU and US versions, with and without GPS)]()

## Potential candidates
* As 4G modem you could basically use anything that provides a RNDIS interface. Best option is something that also provides a serial interface to commuincate with the modem to get signal quality information. This is not mandatory, but makes debugging easier.

* Any multi-core RPi with at least 512MB should be fine here. We rely on a hardware encoder for h264 encoding.