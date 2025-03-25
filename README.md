# RC-Streamer - not actually, codename, who knows...

## Configuration
On the server, make sure the following ports are open (you might need to forward them through your router) on your Server:

- 6666: UDP for receiving video
- 6667: UDP for receiving UDP messages

## Setup
Both - client and host need to be set up in order to communicate with each other, follow the setup guides to get everything going.

> This is work in progress, the ultimate goal is to provide a *.deb file for the client to just install and be done with it - we are not at that point yet. Helper scripts are in place to assist you in getting things done.

### Client
You can find a detailed setup guide for the **client** in the [Client](/stylesuxx/rc-stream/tree/master/docs/Client.md) file.

### Host
You can run any flavor of Linux as your host system, you will need to install gstreamer libraries and Python Version `>=3.11.4`.

I suggest you do this via `pyenv`:

```bash
curl -fsSL https://pyenv.run | bash
pyenv install 3.11.4
pyenv global 3.11.4
python --version
```

Then clone the repo, create a `venv` and install dependencies:

```bash
git clone git@github.com:stylesuxx/rc-stream.git
cd rc-stream
python -m venv .
source bin/activate
pip install -r requirements.txt
```

> On the host you will also need gstreamer dependencies installed.

## Usage

### Testing
Follow the [Hepers README](/stylesuxx/rc-stream/tree/master/docs/Client.md) to make sure your setup is capable of streaming in real-time.

### Bash scripts
The bash script directory contains `gstreamer` related functionality. Execute `send_cam.sh` on the client to send video to the server. Execute `gst-udp-sink.sh` on the server to receive video from the client.

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

### DEB Packages
The `./build` directory contains build scripts and skeleton directories for creating Debian packages. When publishing a new release, those packages should be attached.

Build the packages on the target system:

```bash
cd ./build
./build.sh
```

The `*.deb` files can then be found in `./tmp` directory.`
