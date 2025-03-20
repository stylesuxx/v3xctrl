# RC-Streamer - not actually, codename, who knows...

## Terminology
`client` is the RPI with the 4G Modem.
`server` is the computer that the client is sending it's data to and which handles displaying video and sending control data.

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

### Hardware selection
'Raspberry Pi Zero 2 W' has most of what we need:
* small size
* widely available
* hardware video encoder
* dedicated camera platform
* Wifi
* GPIO

The 'RPi Zero 2 W' has no issues encoding video streams in realtime in 1920x1080@30fps. This will only be feasible with high bandwith 4G modems but obviously lower resolution won't be an issue either.

Additional sensors:
* INA219 for measuring battery voltage

Actuators:
* Speedcontroller (PWM based) - preferably with BEC to supply Servo(s) with power
* Servo(s) (PWM based)

Power supply:
* Step down converter to provide stable 5V@3A

4G Modem - as long as it provides a rndis device, any is fine - as mentioned above, higher category is preferred.

## Configuration
On the server, mak sure the following ports are open (you might need to forward them through your router):

- 6666: UDP for receiving video
- 6667: UDP for receiving UDP messages

## Control channel
The control channel is be-directional, but has to be initialized by the client in order to punch a hole for UDP in the NAT.

Both, client and server have to establish a UDP Sender and Receiver.

There are a couple of Messages defined:

* Syn
* Ack
* Heartbeat
* Command
* Telemetry
* Control

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

### Typical sizes

A Syn and Ack package have the same size, no payload and their classname is the
same length: 21bytes

A Control package containing a value for steering and one for throttle has a length of 35bytes

### Considerations

The size we want to transmit really depends on how much the input values will change. Since the input is queried in a *game loop*, this is our limiting factor. It will be between 30Hz - 100Hz, control packets will need to be sent in that speed (only if the value changes, but at least, 1 time a second to keep the client alive).

### Savings

Technically we could save a couple of byte by truncating the timestamp, also when using payload, keep the keys short.

## Installation
Create a `venv`, activate it, and install dependencies (do this on both - client and server):

```bash
python -m venv .
source bin/activate
pip install -r requirements.txt
```

Make sure to use at least Python Version `3.11.4`. Use pyenv to easily manage your Python versions. Make sure you have enough RAM - or SWAP for that matter - to download and compile python. RPI Zero has 4 cores but only 512MB RAM. Either reduce the amount of cores used during compilation or add SWAP (I used 8GB to be on the save side.)

## Usage

### Helpers
The `helpers` directory contains a few helper scripts that can be used to test the server and client.

Usage should be pretty self-explanatory:

```bash
# On server start the server helper
python helpers/self_test/server.py 6666

# On client, run the client helper with the servers IP and port
python helpers/self_test/client.py 192.168.0.1 6666
```

Output will be displayed from the server script.

### Bash scripts
The `bash` directory contains a few bash scripts that might be usefull for quickly testing different gstreamer pipelines.

### Server
On the server invoke:

```bash
python src/server.py $PORT
```

The Server will bind to the given port and start listening for UDP packets from the client. Once a SYN packet is received from the client, the server will send one ack package and then continue sending `Command` packets every second.

The server will run connectivity checks. If no new packages has been seen from the client in a specified time frame, the connection is deemed disconnected and the server will exit.

### Client
On the RPI invoke:

```bash
python src/client.py $HOST $PORT
```

On the client we can not bind to a specific port, instead we use one socket to send packets and to listen to. The first SYN package sent, basically opens up a hole through which the server can send packets back to the client.

Once the initial SYN/ACK packages have been exchanged, the client will start sending telemetry packets every second.

Similar to the server, the client is also running those sanity checks and will also exit if no package has been seen in a specified amount of time.

The client should definetly have the shorter threshold for those checks in order to not lose control over the attached device.


## Development

### Tests
Run all tests:

```bash
python -m pytest tests
```

Watch for file changes and re-run tests automatically:

```bash
python watch_tests.py
```
