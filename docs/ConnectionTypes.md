# Connection Types
There are several connection types available:


## Direct
The Viewer has a static IP and reserved ports to which the streamer can connect.

> This is the simplest, most reliable and recommended connection type for most use cases.

## Relay
If both the streamer and viewer are behind mobile NATs, lack a dedicated IP, or you have no control over port forwarding, a relay connection can be used as a fallback option.

In this setup, both the viewer and streamer send their control and video data to a relay server, which then forwards the data between them. This approach is more complex and should only be used when a direct connection is not possible.

### Caveats
Using a relay server adds a small amount of latency and depends on external infrastructure, which can sometimes be less reliable. We strive to keep our relay server highly available, but nothing beats a direct connection.
