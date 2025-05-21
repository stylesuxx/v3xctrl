# Connection Types
There are multiple connection types that can be used:


## Direct
The server has a static IP and reserved ports to which the client can connect. This is the simplest and recommended connection type for most use cases.

## Rendezvous
If the server is also behind a mobile NAT, and does not have a dedicated IP or you have no control over port forwarding, this is a fallback option. In this case, both client and server will meet at an external rendezvous point, exchange connection details and punch holes through the NATs in order to have peer to peer communication that way. This is more complex and should be used only as a last resort.

### Caveats
Using a rendezvous server for UDP hole punching comes with a couple of caveats:

1. If both - client and server - are on the same mobile network and get the same external IP, it is likely that the connection will not work since most routers will not apply port forwarding when traffic is not coming from the outside.

> **Mitigation**: Make sure you are using different providers for client and server.

2. Some CGNATs are symmetrical. This basically prevents hole punching all together, since the outbound port depends on the outbound address (IP & Port).
