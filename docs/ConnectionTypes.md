# Connection Types
There are multiple connection types that can be used:


## Direct
The server has a static IP and reserved ports to which the client can connect.

> This is the simplest, most reliable and recommended connection type for most use cases.

## Relay
If streamer and viewer are both behind a mobile NAT, and do not have a dedicated IP or you have no control over port forwarding, this is a fallback option.

In this case, both viewer and streamer will send their control and video data to a relay server, which will relay the data between them. This is more complex and should only be used when a direct connection is not an option.

### Caveats
Using a relay server adds some latency (although it is minimal). You also need to rely on external infrastructure, which can be unreliable. We try to keep our relay server as reliable as possible, but nothing beats a direct connection.
