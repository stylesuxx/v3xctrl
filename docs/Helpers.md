# Helpers
There are a couple of helper scripts that are used for testing and debugging. They are located in the `helpers` directory.

## Selftest
`client.py` and `server.py` will run a selftest on the client and server respectively. They will send a few packets and check if they are received correctly. If they are not received correctly, they will print an error message.

```bash
# On server start the server helper
python helpers/self_test/server.py 6667

# On client, run the client helper with the servers IP and port
python helpers/self_test/client.py 192.168.0.1 6667
```

> Output will be displayed from the server script.

There are 4 tests that will be run in succession:

1. Bandwith from Client to server - higher is better, the default video pipeline will need a bandwith of 3Mbps.
2. Bandwidth from Server to client - higher is better, at least 300kbps are required here.
3. UDP latency - lower is better. Single direction time is estimated by just taking half of the RTT (Round trip time). The higher this time is, the more lag you will feel - 30-50ms per direction or 60-100ms RTT are acceptable here. Also make sure that Lost is close to 0.
4. UDP hole lifetime - checks how long the hole stays open after the client initially punches a hole through the NAT. We abort after 10 seconds, this is plenty to keep communication open since the client will send a heartbeat message at least once per second.

### UDP
In the `udp` folder you will find a dedicated test for profiling UDP performance. This is mainly useful if you want to compare carrier and see which time of the day/week has the lowest latency.

The script will run for 24hours, logging count, loss mean, min and max RTT every 10 minutes by default. The output is in TSV format and can be piped into a file for later analysis.

```bash
# On server:
python ./helpers/self_test/udp/server.py 6666

# On client:
python ./helpers/self_test/udp/client.py 192.168.0.1 6666

# On client with different interval
python ./helpers/self_test/udp/client.py 192.168.0.1 6666 --interval 5

# On client log to file and print to stdout every minute
python -u ./helpers/self_test/udp/client.py 192.168.0.1 6666 --interval 1 | tee - a results.tsv
```
