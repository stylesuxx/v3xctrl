# End-to-end harness

Drives the desktop viewer and a real streamer through every supported
connection permutation and decides pass/fail from the viewer's log and the
streamer's journal. Tracks issue #691.

Everything lives in this folder. Nothing under `src/` depends on it, and the
deb build never copies it. The harness imports read-only helpers from `src/`
(the relay connection check, the transport enum) and runs from the repo venv.

## Layout

```
e2e/
  README.md
  __main__.py                        entry point: `.venv/bin/python e2e ...`
  requirements.txt                   python-evdev for the virtual gamepad
  udev/70-v3xctrl-e2e-uinput.rules   one-time install, lets your user open /dev/uinput
  agent/streamer_agent.py            stdlib-only script copied to the streamer per run,
                                     run under /opt/v3xctrl-venv/bin/python there
  v3xctrl_e2e/                       orchestrator package
  tests/                             unit tests on captured log text, no hardware
  runs/                              artifacts, gitignored
```

## One-time setup on the viewer machine

```bash
.venv/bin/pip install -r e2e/requirements.txt
sudo install -m 644 e2e/udev/70-v3xctrl-e2e-uinput.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger /dev/uinput
```

Log out and in again once so the `uaccess` tag applies to your session. The
harness checks `/dev/uinput` in preflight and tells you if this is missing.

## Prerequisites on the streamer

- Reachable over SSH with key login, passwordless sudo for that user. Users
  created by Raspberry Pi Imager have this unless the newer "passwordless
  sudo" checkbox was left off.
- The v3xctrl image: the agent runs under `/opt/v3xctrl-venv/bin/python`,
  the interpreter the streamer services use.
- Nothing else loading the Pi. Preflight reads the load average and refuses
  above `--max-load-per-cpu` (default 0.75), because a busy Zero 2 W turns a
  one second SSH round trip into minutes and wrecks every timing assertion.
- A relay session ID dedicated to testing. Every relay test registers and
  overwrites the session for that ID.
- No camera is needed. Every streamer config sets `video.testSource` on, or
  off with `--camera`, and `video.autostart` is always forced on because the
  service manager only starts the video service when it is set.

## Running

```bash
.venv/bin/python e2e --only viewer --relay-id <session id>            # viewer against the relay, no Pi needed
.venv/bin/python e2e --streamer-host 192.168.1.225 --ssh-user chris \
    --relay-id <session id> [--relay-host relay.v3xctrl.com:8888]        # positive viewer, local and relay cases
.venv/bin/python e2e --streamer-host 192.168.1.225 --ssh-user chris \
    --relay-id <session id> --spectator-id <spectator id> --negative     # all 20 cases
```

Without `--negative` the mismatch and wrong-ID cases are left out, without
`--spectator-id` the spectator cases R6 to R10 are; the run says at its start
which groups it skips.

Useful flags:

| Flag | Effect |
|---|---|
| `--only viewer` / `--only local` / `--only relay` | one phase, repeatable; `viewer` needs no streamer, `local` needs no relay ID |
| `--negative` | add the mismatch and wrong-ID tests |
| `--case NAME` | run only this case, repeatable; names as in the tables below |
| `--spectator-id ID`, `--spectator-seconds N` | add the spectator soak cases to the relay phase |
| `--viewer flatpak` | test the installed `com.v3xctrl.viewer` instead of the source tree |
| `--viewer-source DIR` | `src` directory of another viewer checkout, for example a worktree of a feature branch |
| `--camera` | stream from the camera, `video.testSource` off |
| `--without-gamepad` | skip the virtual gamepad and the input scenario |
| `--headless` | run the viewer under the SDL dummy video driver |
| `--steady-seconds` (at least 20), `--connect-timeout`, `--min-fps`, `--max-drop-rate`, `--telemetry-tolerance` | thresholds |

`drop_rate` in the viewer's receiver stats counts frames the viewer skipped on
purpose to keep latency down when rendering fell behind arrival. It measures
render pacing on the viewer machine. A Zero 2 W test source shows 2 to 3
percent over direct TCP, where nothing can be lost in transit, and 7 percent
over the TCP relay, where frames arrive in bunches. Link problems show up as
`No frames received`, low `avg_decoded_fps` and high `max_jitter`.

Exit code 0 means every test passed, 1 means at least one failed, 2 means
preflight refused to start.

## What a run does

1. Copies the agent to the streamer and starts it in one multiplexed SSH
   session. The agent speaks the harness's own shape: `open_run` snapshots
   `config.json`, `begin_case` follows the journal from before the restart
   and applies a config, `end_case` stops following, `close_run` restores
   the snapshot, also on abort. A snapshot left behind by a run that was
   killed is reused as the original config, with a warning. `open_run` also
   stops the stream units, so a control service autostarted before the run
   cannot answer the first case's viewer and then get restarted under it. The order that
   keeps journal lines from being lost lives in the agent, so the orchestrator
   cannot get it wrong.
2. Runs preflight: agent reachable, load, local ports free, display, GStreamer
   available in the viewer interpreter, `/dev/uinput` writable, relay session
   ID valid.
3. Creates the virtual gamepad and asks pygame, in the viewer's interpreter,
   which GUID it assigned. That GUID and an ideal calibration block go into
   every viewer config, so the gamepad chain (config load, calibration,
   button assignment) is exercised implicitly.
4. For each test case: writes a fresh `settings.toml`, starts the viewer with
   `--connect` and `--title` naming the case and its position in the run (the
   spectator's window carries the same name with `spectator` appended), begins
   the case on the streamer (only the `viewer`,
   `development` and `video` keys change, `network` is never touched;
   `v3xctrl-service-manager` restarts on the new config), waits for the
   connection signals, holds a steady window, and evaluates. Ending the case
   stops the video and control units, so the next case's viewer, which starts
   before its config is applied, can only connect to the services that apply
   starts.
5. L1 additionally drives throttle, steering, trim and recording through the
   gamepad and verifies from the control journal that the pulse widths move
   and settle, then stops and restarts the video and control services and
   checks the viewer notices both.

## Test matrix

Viewer only, no streamer involved. The relay answers a registration only once
both peers are present, so these prove the viewer's side of the setup:

| Test | Mode | Checks |
|---|---|---|
| V0-bootstrap | direct udp, no settings file | viewer creates a complete settings file, GStreamer receiver chosen |
| V1-viewer-direct-tcp | direct tcp | both TCP servers listening |
| V2-viewer-relay-udp | relay udp | sockets bound, video and control announcements sent, no rejection |
| V3-viewer-relay-tcp | relay tcp | both tunnels started and their proxies bound, no failed TCP connect |
| V4-viewer-relay-wrong-id (`--negative`) | relay udp | the relay rejects the ID |
| V5-viewer-relay-tcp-wrong-id (`--negative`) | relay tcp | both tunnels report the rejected handshake |

Local, direct mode with the viewer's LAN address as `viewer.direct.host`:

| Test | Streamer | Viewer | Checks |
|---|---|---|---|
| L1-direct-udp-udp | udp | udp | connect, video flowing, input scenario, fault injection |
| L2-direct-tcp-tcp | tcp | tcp | connect, video flowing |
| L3, L4 (`--negative`) | mismatched | | the failure is reported, no connection |

Relay: R1 to R4 cover udp/udp, tcp/tcp, udp/tcp and tcp/udp. R5
(`--negative`) uses a wrong session ID and expects the rejection on both sides.

Spectator soak, with `--spectator-id`: R6 (udp) and R7 (tcp) connect the
primary viewer as usual, then start a second viewer in spectator mode on its
own local ports (16388 and 16390) and hold both for `--spectator-seconds`
(default 60, twice the relay's 30 s spectator timeout; pass 300 or more for a
soak). The spectator must reach `Pipeline is now PLAYING`, keep its
frame rate, and never log `No frames received`. Its lines appear as
`spectator` in the timeline and its output goes to `spectator.log`. R8 (udp)
and R10 (tcp) replay a viewer switching to spectator mode: the primary viewer
connects and is stopped, then the spectator starts on the viewer's own ports,
so the relay sees it from the address it knows as the viewer. R9 has viewer
and spectator connected together, stops the viewer, and requires the
spectator to lose its video within the relay's registration lifetime.

## Reading the artifacts

`e2e/runs/<timestamp>/summary.json` and one directory per test with:

- `timeline.log`: viewer lines and streamer journal lines on one clock
- `viewer.log`: the raw viewer output
- `settings.toml` (the file the viewer ran with, copied to `viewer-settings.toml`)
  and `streamer-config.json`: exactly what was under test
- `result.json`: pass/fail, failure messages, notes such as apply duration

## Unit tests

```bash
.venv/bin/python -m pytest e2e/tests
```

They run on captured log text with fake clocks and fake transports and never
touch a device. `ruff` and `mypy` cover this folder like the rest of the repo.

Error lines the viewer writes while it is being torn down (an aborted relay
registration, the streamer losing its control peer) are outside the window
the forbidden rules cover. A rule that hits more than once is reported as one
line with the count, the time span and the first offending line.

## Known limits

- SDL numbers joystick axes and buttons by ascending evdev code. The binding
  relies on that; if pygame ever reports a different order, the input scenario
  fails with "pulse width moved 0us" and the timeline shows which axis moved.
- The input scenario reads the streamer's per-message mixer output with
  channel A as throttle and channel B as steering, so its axis checks hold for
  the Ackermann mixer only.
- The keyboard input path is not covered.
- A locally started relay server is not covered; every relay case uses the
  configured relay host.
- The Flatpak viewer kind needs a Flatpak built from a branch that has the
  `--connect` flag; preflight checks the viewer's `--help` and says so. A
  build without `--title` still runs, with untitled windows and a warning.
