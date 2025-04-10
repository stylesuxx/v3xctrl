## Terminology
- `client` is the hardware platform (RPI with the 4G Modem).
- `server` is the computer that the client is sending video to and which handles displaying video and sending control data.
- `UDP` is the protocol used for sending video and control data.
- `h264` is the codec used for encoding video: high compression efficiency, good video quality at lower bitrates, widely supported in hardware encoders
- `python` is the programming language most of this project is written in. We use a custom version of python on the client to ensure compatibility on different flavours of debian based operating systems.
