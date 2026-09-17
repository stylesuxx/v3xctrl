# WiFi soak test

Reproduces the brcmfmac/SDIO WiFi failure on the Raspberry Pi Zero 2 W
(stylesuxx/v3xctrl#688): `mmc1: Controller never released inhibit bit(s)`.
Deployed to a Pi for the test, removed afterwards. Not part of the image.

## Requirements

| Where | What |
|---|---|
| Host | Linux, `iperf3`, ssh access to the Pi |
| Pi | Zero 2 W, Raspberry Pi OS, `iperf3`, user with passwordless sudo |
| Pi, optional | `stress-ng` for the heat load, `rpicam-vid` for the camera load |

## Quick start

1. Start one iperf3 server per direction on the host:

   ```sh
   iperf3 -s -p 5201 -D
   iperf3 -s -p 5202 -D
   ```

2. Set `IPERF_SERVER` in `wifi-soak.conf` to the host's LAN address.

3. Install. The Pi reboots into the first cycle:

   ```sh
   ./deploy.sh install pi@<pi-address>
   ```

4. Check after a few hours:

   ```sh
   ./deploy.sh status pi@<pi-address>
   ```

5. Pack everything for the issue, then remove:

   ```sh
   ./deploy.sh bundle pi@<pi-address>
   ./deploy.sh remove pi@<pi-address>
   ```

   `bundle` prints the status and writes `results/<host>-<timestamp>.tar.gz`.
   Attach that archive, it holds everything needed to interpret the run.

## Commands

| Command | Effect |
|---|---|
| `deploy.sh install <target>` | Copy files, enable the service, reboot into the first cycle |
| `deploy.sh status <target>` | Counts per outcome and one line per hit |
| `deploy.sh details <target>` | `status` plus events, snapshots and sampler lines per hit |
| `deploy.sh fetch <target>` | Copy `/var/log/wifi-soak` into `./results/<host>-<timestamp>/` |
| `deploy.sh bundle <target>` | `fetch` plus status, details, system info, config and the kernel journal of all boots, packed into `./results/<host>-<timestamp>.tar.gz` |
| `deploy.sh stop <target>` | End the running cycle without reboot, pause the loop |
| `deploy.sh resume <target>` | Clear the pause, start a cycle now |
| `deploy.sh remove <target>` | Revert everything the installer changed, keep the logs |
| `deploy.sh purge <target>` | `remove` plus delete the logs |

## Configuration (`wifi-soak.conf`)

| Variable | Default | Meaning |
|---|---|---|
| `IPERF_SERVER` | `192.168.1.100` | Host running the iperf3 servers, also the ping probe target |
| `IPERF_PORT` | `5201` | Server port for the Pi to host stream |
| `IPERF_ARGUMENTS` | `-u -b 5M -l 200` | Pi to host stream, iperf3 client flags |
| `IPERF_REVERSE_PORT` | `5202` | Server port for the host to Pi stream |
| `IPERF_REVERSE_ARGUMENTS` | `-u -b 5M -l 200` | Host to Pi stream, empty disables it |
| `CYCLE_SECONDS` | `600` | Cycle length, the Pi reboots when it expires |
| `REBOOT_ON_HIT` | `0` | `1` reboots at the first signature, `0` keeps the load running to the cycle end |
| `NETWORK_TIMEOUT_SECONDS` | `300` | Wait for wlan0 and the server after boot before recording `no-network` |
| `HEAT_LOAD_CPUS` | `2` | Cores burned with stress-ng, `0` disables |
| `CAMERA_STREAM` | `0` | `1` runs rpicam-vid 1280x720 at 30 fps, 1.8 Mbit H.264 over UDP |
| `CAMERA_PORT` | `5000` | UDP port for the camera stream |

## One cycle

1. Boot, wait for wlan0 and a ping reply from `IPERF_SERVER`.
2. Start the sampler, the heat load, the camera load, the iperf3 clients.
3. Follow the kernel log for the failure signatures.
4. First signature: record `hit`, take a state snapshot. `REBOOT_ON_HIT=1`
   ends the cycle here.
5. `CYCLE_SECONDS` expired: record `hit-end` or `clean`, dump dmesg, reboot.

A frozen WiFi never stalls the loop, the Pi judges itself from its own kernel
log. A hard kernel hang is caught by the hardware watchdog and shows as a
`started` line without a result.

## Results

`status` output:

```
cycles=50 hit=6 clean=37 no-network=0 stopped=8
started but never finished, hard hangs or watchdog resets: 0
boots in the persistent journal: 43, signature lines across them: 6

cycle              hit_at     temp  signatures  events link_at_end
20260917T191017      134s   77.9'C           1       3 alive
20260917T212139      417s   77.9'C           1       3 alive
```

| Outcome | Meaning |
|---|---|
| `started` | Cycle began, written right after boot |
| `hit` | First failure signature, uptime is the time to failure |
| `hit-end` | Cycle end after a hit: number of signatures and warnings, `link=alive` or `link=dead` from a ping |
| `clean` | Full cycle without a signature |
| `no-network` | WiFi not usable within `NETWORK_TIMEOUT_SECONDS` after boot |
| `stopped` | Ended by `deploy.sh stop` |
| `started` without a result | Hard hang, watchdog reset or power loss |

Per cycle files in `/var/log/wifi-soak/cycles/<cycle-id>.*`:

| File | Content |
|---|---|
| `sampler` | 1 Hz: temperature, throttle flags, ARM/core/EMMC clocks, core voltage, signal and rate, tx/rx Mbit and packets per second, failed frames, mmc1 interrupts per second, server reachability, SDIO bus clock |
| `iperf`, `iperf-rx` | Per second iperf3 output for each direction |
| `trigger` | Failure signature lines |
| `events` | Signature and warning lines |
| `state-hit`, `state-end` | Throttle flags, mmc1 ios, interrupt counts, link, station dump, interface counters, dmesg tail |
| `dmesg` | Full kernel log at the cycle end |
| `camera` | rpicam-vid output when enabled |

The persistent journal keeps the kernel log of every boot: `journalctl -k -b -N`
on the Pi shows boot N back, `journalctl -k -b all` all of them.

Sampler columns at a hit: `tx`, `rx` and `irq` give the load, `throttled` and
the clocks show whether anything changed before the event, `reach` whether the
server was still reachable after it.

## Findings with the default configuration

Stock Zero 2 W, kernel 6.18.29, WiFi firmware 7.45.96.s1, bare 5 V supply,
nothing attached, default `wifi-soak.conf`.

| Condition | Result |
|---|---|
| 200 byte UDP, 5 Mbit/s each way, about 3100 packets/s per direction, 2 cores stress-ng | Signature about once per hour of load, 6 hits in 43 cycles |
| Time into the cycle at the hit | 109 to 496 s, no pattern |
| Temperature and throttling at the hit | 75 to 79 degrees, `throttled=0x0`, clocks flat |
| Cost of a hit | One SDIO transfer aborted, link stayed up in every observed cycle |
| 1400 byte UDP, transmit only, 47 Mbit/s, 4 hours, including 80 degrees with thermal capping | No signature |

## What the installer changes on the Pi

| Path | Purpose |
|---|---|
| `/opt/wifi-soak/` | Scripts and config |
| `/etc/systemd/system/wifi-soak.service` | Runs one cycle per boot, enabled |
| `/etc/systemd/system.conf.d/wifi-soak-watchdog.conf` | `RuntimeWatchdogSec=30` |
| `/etc/systemd/journald.conf.d/zz-wifi-soak.conf` | `Storage=persistent`, Raspberry Pi OS ships journald volatile |
| `/etc/ssh/sshd_config.d/wifi-soak.conf` | `IPQoS cs6 cs6`, keeps ssh usable while the WiFi queue is full |
| `/var/log/journal/` | Created when missing |
| `/var/log/wifi-soak/` | Results |

`remove` reverts all of it except `/var/log/wifi-soak/`, `purge` deletes that too.
