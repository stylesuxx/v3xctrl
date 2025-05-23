# Latency
Here is a flow chart showing the latency in the system. We need to consider two chains:

- The client-to-server chain (video)
- The server-to-client chain (control)

Looking at the chart makes it clear that there is a lot of potential for introducing latency, and only some of the stages are under our control:

```
-----------
| Client  |
-----------
| Camera  | 15–25 ms (may increase in low light)
| Encoder | 3 ms
| UDP     | 0.5–1.5 ms (RTP packaging + kernel/network stack delay)
-----------
| Network | 20–40 ms (4G latency, variable)
-----------
| Server  |
-----------
| UDP     | 0.5–1.5 ms
| Decoder | 1–3 ms
-----------
| Display | 2–8 ms
-----------
```

So from capturing a frame to displaying it on the screen, it takes **42–82 ms on average**.
This heavily depends on the network, and latency spikes are possible.


```
------------
| Server   |
------------
| Control  | 0.1–0.3 ms (command generation & queuing)
| UDP      | 0.5–1.5 ms (kernel stack, NIC buffer)
------------
| Network  | 20–40 ms (4G latency, variable)
------------
| Client   |
------------
| UDP      | 0.5–1.5 ms (receive, buffer copy)
| Process  | 0.5–2 ms (command parsing & execution)
------------
| Actuator | 1–5 ms (GPIO/PWM write, driver delay)
------------
```

From seeing the image, reacting to it, and sending a control packet back to the client, it takes **22.6–50.3 ms**.

This means we have a total, combined latency (end to end) of 64.6ms - 132.3ms.

> **End to end latency below 150ms is generally considered acceptable for responsive remote control.**

> **NOTE**: You can clearly see, that our **largest contributor to latency is in the network**. Choosing a good, reliable 4G provider is crucial for a smooth user experience.


## UDP Relay
When using the UDP Relay instead of the direct connection, the latency increases slightly.
