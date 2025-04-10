# Control channel
The control channel is bi-directional, but has to be initialized by the client in order to punch a hole for UDP in the NAT.

Both, client and server have to establish a UDP Sender and Receiver.

There are a couple of Messages defined:

* Syn
* Ack
* Heartbeat
* Telemetry
* Control
* Command

The control flow is as follows:

1. Client sends a Syn message to the server.
2. Server responds with an Ack message.
3. Client sends either Telemetry, Command or Heartbeat messages.
3. Server Sends either Telemetry, Command or Control messages

All of the above messages are subclassed from `Messasge`, when sending the package, we are extracting data from the Message into a dict and using msgpack for packing and unpacking. This allows us to re-build a Message object on the other end. This is *NOT* the most resource effective thing to do, since it comes
with a bit of overhead, however it is very convenient to implement, use, extend and debug.

Every package contains the following information:
* `type`: The type of message, so we know which class to use to put it back together
* `timestamp`: In order to have sequencing, this will allow us to decide if we
want to keep the packet, or discard it for being out of order
* `payload`: the actual payload of the message. Sometime it is enough to just have type and timestamp, then payload will be empty

## Typical sizes
A Syn and Ack package have the same size, no payload and their classname is the
same length: 21bytes

A Control package containing a value for steering and one for throttle has a length of 35bytes

## Considerations
The size we want to transmit really depends on how much the input values will change. Since the input is queried in a *game loop*, this is our limiting factor. It will be between 30Hz - 100Hz, control packets will need to be sent in that speed (only if the value changes, but at least, 1 time a second to keep the client alive).

## Savings
Technically we could save a couple of byte by truncating the timestamp, also when using payload, keep the keys short.
