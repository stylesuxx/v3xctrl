## Terminology
- `streamer` is the hardware platform (RPI with the 4G Modem).
- `viewer` is the computer that the **streamer** is sending video to and which handles displaying video and sending control data.
- `UDP` is the protocol used for sending video and control data.
- `h264` is the codec used for encoding video: high compression efficiency, good video quality at lower bitrates, widely supported in hardware encoders
- `python` is the programming language most of this project is written in. We use a custom version of python on the client to ensure compatibility on different flavours of debian based operating systems.
- `relay` is a mechanic used if the **viewer** does not have a fixed IP address and instead is also on a mobile network. A relay is then used to connect streamer and viewer with each other.
