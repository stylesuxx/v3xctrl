# RC-Streamer - not actually, codename, who knows...

## Configuration
On the server, mak sure the following ports are open (you might need to forward them through your router) on your Server:

- 6666: UDP for receiving video
- 6667: UDP for receiving UDP messages

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
On the client invoke:

```bash
python src/client.py $HOST $PORT
```

On the client we can not bind to a specific port, instead we use one socket to send packets and to listen to. The first SYN package sent, basically opens up a hole through which the server can send packets back to the client.

Once the initial SYN/ACK packages have been exchanged, the client will start sending telemetry packets every second.

Similar to the server, the client is also running those sanity checks and will also exit if no package has been seen in a specified amount of time.

The client should definetly have the shorter threshold for those checks in order to not lose control over the attached device.

> This is also the file you want to use as your main entry point for custom client functionality.

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
