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

## Installation
Create venv, activate it, and install dependencies (do this on both - client and server):

```bash
python -m venv .
source bin/activate
pip install -r requirements.txt
```

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
