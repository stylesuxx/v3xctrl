# Control Channel

The control channel is **bi-directional**, but it must be **initialized by the streamer** to punch a UDP hole through NAT.

Both the streamer and viewer establish their own **UDP sender and receiver** sockets.

Communication is handled via a lightweight protocol with the following message types:

* Syn
* Ack
* SynAck
* Heartbeat
* Telemetry
* Control
* Command
* CommandAck
* Latency
* Error
* PeerAnnouncement
* PeerInfo

## Message Flow

1. Streamer sends a `Syn` message to the viewer.
2. Viewer responds with an `Ack` (or `SynAck`) message.
3. Streamer periodically sends `Telemetry`, `Latency`, or `Heartbeat` messages.
4. Viewer responds with `Command`, `Latency`, or `Control` messages as needed.

## Message Format

All messages subclass a common `Message` base class. Each message is serialized into a `dict` and packed using **msgpack**. On the receiving side, the data is unpacked and reconstructed into the appropriate `Message` object.

This approach is **not the most resource-efficient** due to serialization overhead, but it is simple to implement, extend, and debug.

Each packet includes:
* `type` — identifies which message class to reconstruct
* `timestamp` — allows sequencing and discarding out-of-order packets
* `payload` — the message data (can be empty for simple messages)

## Typical Packet Sizes

* `Syn` or `Ack`: ~21 bytes (no payload, fixed class name length)
* `Control`: ~35 bytes (contains steering and throttle values)

## Frequency Considerations

Control packets are sent based on input changes. Input is sampled in a **game loop (30–100 Hz)**, so packets are transmitted at that rate **only if values change**, with at least one packet per second to keep the connection alive.

## Potential Optimizations

* Truncate timestamps to save a few bytes.
* Use shorter payload keys to further reduce packet size.
