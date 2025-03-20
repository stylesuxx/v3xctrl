# Motivation

## Thoughts and consideration
Low latency is our #1 priority, the technologies are chose accordingly. Since we do not want to re-invent the wheel (yet) we can chose the best layer 4 protocol for our use case. UDP and QUIC are both viable options. Since we are consistently updating in both directions, reliability is not super important, we can handle a couple of lost (and out of order) packages by dealing with sequencing on client/server.

UDP in context of a 4G networks has a couple downsides:
1. Some carriers might not allow UDP at all (at least some sources on the web make it seem like that, personally not encountered this)
2. 4G often uses CGNAT, it boils down to this: the client does not have a dedicated public IP address. This means that we need to rely on UDP hole punching.  This means, that the client has to send the initial packet which opens a hole on the NAT and allows the server to respond through this hole. Hole in this context is simply a port which is kept open and directs traffic to the client. The client needs to send UDP packages to keep the hole open, which is not a big deal, since we want transmit telemetry data to the server anyway.

Bandwith matters - 4G has multiple categories, the lowest one has a 5Mbps upload limit - this means our video and data streams need to stay below that. This is the best case though, when reception is bad, bandwith can drop significantly below that. Optimally the 4G modem has the highest category available. For breakout boards this seems to be CAT4 - boasting 50Mbps upload. Also the consumer USB sticks are mainly in this category.

Also consider the data limit of your provider. If we are looking at a 1920x1080, 30fps stream with I frames every 2 seconds this can easily be 8Mbps (in decent quality) - this accumulates to 3.6GB per hour. If we are looking at a 720, 30fps stream instead, this is reduced to 5Mbps or 2.25GB/h.

### Recommended settings
Good settings can be easily recommended by a set of self tests:

* Bandwidth: upload 10MB to server - this will give us bandwith limitations and help us adjust resolution and bitrate
* UDP: Round trip time - to check if the latency is at a usable level
* UDP: Hole duration - how long does a punched hole stay open. Technically everything above a second is more than enough. Telemetry we can send every second and reply with control packets every couple of milli seconds.
