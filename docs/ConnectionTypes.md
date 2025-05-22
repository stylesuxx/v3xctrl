# Connection Types
There are multiple connection types that can be used:


## Direct
The server has a static IP and reserved ports to which the client can connect. This is the simplest and recommended connection type for most use cases.

## Relay
If the server is also behind a mobile NAT, and does not have a dedicated IP or you have no control over port forwarding, this is a fallback option. In this case, both client and server will send their control and video data to a relay server, which will relay the data between them. This is more complex and should be used only as a last resort.

### Caveats
Using a relay server adds some latency (although it is minimal). You also need to rely on external infrastructure, which can be unreliable.
