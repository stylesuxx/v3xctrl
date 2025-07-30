# Latency

This flow chart illustrates where latency occurs in the system. We consider two chains:

- Streamer -> Viewer (video path)
- Viewer -> Streamer (control path)

There are multiple stages where latency is introduced, and only some of them are under our control:

```
------------
| Streamer |
------------
| Camera   | 15–25 ms (sensor exposure & frame readout, may increase in low light)
| Encoder  | 3-6 ms (H.264 hardware encoder, resolution and bitrate dependent)
| UDP      | 0.5–1.5 ms (RTP packaging + kernel/network stack delay)
------------
| Network  | 20–40 ms (typical 4G RTT, variable; occasional spikes possible)
------------
| Viewer   |
------------
| UDP      | 0.5–1.5 ms
| Decoder  | 1–3 ms (hardware-accelerated H.264 decode)
------------
| Display  | 2–8 ms (OS buffering, vsync interval, display refresh delay)
------------
```

From capturing a frame to displaying it on-screen, the average latency is roughly **42–84 ms**, depending on network conditions. Latency spikes beyond this range are possible during poor signal quality or congested networks.


```
------------
| Viewer   |
------------
| Control  | 0.1–0.3 ms (input event handling, message queueing)
| UDP      | 0.5–1.5 ms (kernel stack, NIC buffer)
------------
| Network  | 20–40 ms (typical 4G RTT, variable)
------------
| Streamer |
------------
| UDP      | 0.5–1.5 ms (receive, buffer copy)
| Process  | 0.5–2 ms (command parsing & execution)
------------
| Actuator | 1–5 ms (GPIO/PWM write, motor driver response time)
------------
```

From reacting to a video frame and sending a control packet back to the streamer, the control latency is typically **22–50 ms**.

## Total End-to-End Latency

Combined latency is therefore in the range of 65–135 ms, under normal conditions.

> End-to-end latency below ~150 ms is generally considered acceptable for responsive remote control.
> The **largest contributor** to latency is the **cellular network**. Choosing a strong, low-congestion 4G provider is crucial for good performance.


## UDP Relay
When using a UDP Relay instead of a direct connection, expect **additional latency of 2–8 ms** due to extra packet processing and routing through the relay server. The increase is typically negligible compared to total 4G latency but may add up if the relay server is geographically distant.
