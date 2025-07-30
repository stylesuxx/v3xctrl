# Motivation

This document explains why certain design choices were made and the reasoning behind the current implementation.

Thoughts and Considerations

Low latency is our **#1 priority**, and all technology choices are made accordingly. Since we do not want to reinvent the wheel (yet), we chose the best Layer 4 (transport) protocol for our use case. **UDP** and **QUIC** are both viable options, but because we are consistently updating in both directions, reliability is less important than speed - we can tolerate a few lost or out-of-order packets by handling sequencing on the streamer/viewer side.

> QUIC is designed for low latency but adds reliability and encryption we don’t need here.

UDP in the context of a 4G networks has a couple downsides:
1. **Carrier restrictions:** Some carriers may filter or rate-limit UDP traffic, though this is uncommon.
2. **CGNAT:** Most 4G networks use Carrier-Grade NAT, meaning the streamer does not have a dedicated public IP. We rely on **UDP hole punching** to establish connectivity:

  * The streamer sends the initial packet to open a port mapping (“hole”) on the NAT.
  * The viewer responds through this hole.
  * The streamer keeps the hole alive by sending periodic UDP packets, which aligns with our need to transmit telemetry data anyway.

> 4G networks often use CGNAT, preventing direct inbound connections; UDP hole punching usually works, but some NAT types or carrier restrictions may require a relay server.

## Bandwidth Constraints

4G networks have multiple categories.

* **Cat 1 LTE** typically achieves 3–4 Mbps uplink in practice.
* Cat 4 supports up to 50 Mbps theoretical uplink, but real-world speeds are typically below 20 Mbps.

Reception quality matters a lot - bad signal can drop bandwidth drastically. Optimally, you should use the highest category modem available.

Also consider data limits:

* A 1080p 30fps stream with I-frames every 2 seconds can easily use ~8 Mbps, or 3.6 GB/hour.
* A 720p 30fps stream reduces this to around 5 Mbps, or 2.25 GB/hour.

> Data usage is approximate and depends heavily on scene complexity and encoder settings.

### Recommended Self-Tests

The system can perform basic tests to suggest optimal settings:

* **Bandwidth test:** Upload a 10 MB test file to the viewer to measure available uplink speed and set resolution/bitrate accordingly.
* **UDP RTT:** Measure round-trip latency to check responsiveness.
* **UDP hole duration:** Measure how long NAT mappings stay open. Anything over 1 second is sufficient since telemetry is sent at least once per second, and control packets are typically sent every few milliseconds.

## Packaging

We want installation to be straightforward:

* **Streamer:** Core functionality is packaged as a Debian `.deb` file for easy installation on Raspberry Pi OS.
* **Viewer:** Needs to be cross-platform (Windows, macOS, Linux) without complex setup requirements. This is why **GStreamer is avoided on the viewer side** - its cross-platform support is too unreliable for our needs.

## Configurability

We do not want to limit what users can do with this platform.

* The streamer includes a **web server for configuration**.
* Settings are stored in a **JSON schema**, which is easily expandable and supports user modifications.

## Client Hardware

Multiple hardware platforms could act as the streamer, but we chose the Raspberry Pi Zero 2 W because it provides:

* Small size, lightweight, widely available
* Hardware H.264 video encoder
* Dedicated camera interface (CSI)
* USB and Wi-Fi support
* 2x hardware PWM channels (500 MHz clock, controllable via pigpio)
* GPIO for sensors and actuators

It can encode **1080p@30fps video in real-time** without issues, assuming sufficient modem upload speed. Lower resolutions are easily supported.

Peripheral considerations:

**Sensors:**
* INAxxx for measuring battery voltage
* GPS (?)

**Actuators:**
* PWM-based speed controller (preferably with BEC to power servos)
* PWM servos

**Power supply:**
* Stable 5 V @ 3 A step-down converter

**Modem:**
* Any 4G modem exposing an **RNDIS device**, higher category preferred.

## Software

We chose **PiOS (Bullseye Lite 64-bit)** as the base system.

> **Note:** Bookworm currently has issues with some RNDIS modems, so Bullseye (listed as Legacy in Raspberry Pi Imager) is recommended. Feel free to test Bookworm; any ARM64 Debian-based OS should work if your modem is supported.

We use:

* Python (custom build) for core logic
* GStreamer for video encoding and transmission on the streamer

When preparing the SD card, use the [Raspberry Pi Imager Utility](https://www.raspberrypi.com/news/raspberry-pi-imager-imaging-utility/) and pre-configure Wi-Fi settings for convenience.
