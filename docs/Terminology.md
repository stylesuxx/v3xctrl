# Terminology

* `streamer` - The hardware platform responsible for capturing and streaming video (typically a Raspberry Pi Zero 2 W with a 4G modem).
* `viewer` - The computer that receives the video stream from the streamer, displays it, and sends control data back.
* `UDP` - The transport protocol used for sending both video and control data.
* `h264` - The video codec used for encoding: offers high compression efficiency, good quality at low bitrates, and is widely supported in hardware encoders.
* `python` - The programming language most of this project is written in. We use a custom build of Python on the streamer to ensure compatibility across different Debian-based operating systems.
* `relay` - A mechanism used when the viewer does not have a fixed IP address (e.g., both devices are on mobile networks). The relay server facilitates connectivity between the streamer and the viewer in such cases.
