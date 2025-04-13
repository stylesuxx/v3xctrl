# Self Tests
There are a couple of helper scripts that are used for testing and debugging. They are located in the `self-test` directory.

## Selftest
`client.py` and `server.py` will run a selftest on the client and server respectively. They will send a few packets and check if they are received correctly. If they are not received correctly, they will print an error message.

```bash
# On server start the server helper
python ./self_test/server.py 6667

# On client, run the client helper with the servers IP and port
python ./self_test/client.py 192.168.0.1 6667
```

> Results will be displayed by the server script.

There are 4 tests that will be run in succession:

### TCP Upload
Bandwith from Client to server - higher is better, the default video pipeline will need a bandwith of 3Mbps.

> You should at least reach 4Mpbs here, otherwise you will have to adjust the bitrate accordingly. Make sure your bitrate has headroom to the total bandwith.

### TCP Download
Bandwidth from Server to client - higher is better.

> You should at least reach 300kbps for the control channel to work smoothly. If you reach less here, your connection will be very unstable.

### UDP Latency
Lower is better. Single direction time is estimated by just taking half of the RTT (Round trip time). The higher this time is, the more lag you will feel.

> 20-50ms per direction or **40-100ms RTT** are acceptable here. Also make sure that loss is close to 0%.

### UDP hole duration
Checks how long the hole stays open after the client initially punches through the NAT. We abort after 10 seconds, this is plenty to keep communication open since the client will send a heartbeat message at least once per second.

## Bandwith details
The initial bandwidth test is just a momentary snapshot, there is another tool which will help you profiling your general situation. Reception will differ on where you are. To profile bandwidth in your area, you can use the `bandwith` tests.

On the server run:

```bash
python ./self_test/bandwidth_server.py 6666
```

On the client run:

```bash
screen
python ./self_test/bandwidth_client.py 192.168.0.1 6666 /dev/ttyACM0

# Use [CTRL - a, d] to disconnect from screen
```

`/dev/ttyACM0` is the serial port of your 4G modem. When starting the script on the client, make sure it will run once you disconnect via SSH, so run through `screen`.

Now you can start walking around the area you want to profile. The client will upload 5MB chunks of data every time the RSRP value changes from the last one.

The client will log to stdout, but also to a CSV (`bandwidth_log.csv`) for later analysis.

## UDP
In the `udp` folder you will find a dedicated test for profiling UDP performance. This is mainly useful if you want to compare carrier and see which time of the day/week has the lowest latency.

The script will run for 24hours, logging count, loss mean, min and max RTT every 10 minutes by default. The output is in TSV format and can be piped into a file for later analysis.

```bash
# On server:
python ./self_test/udp/server.py 6666

# On client:
python ./self_test/udp/client.py 192.168.0.1 6666

# On client with different interval
python ./self_test/udp/client.py 192.168.0.1 6666 --interval 5

# On client log to file and print to stdout every minute
python -u ./self_test/udp/client.py 192.168.0.1 6666 --interval 1 | tee results.tsv
```
