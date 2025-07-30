# Development

This document will help you set up your development environment for both the **Streamer** and **Viewer** components.

> If you are just a regular user, you can skip this section.

## Reference Implementations

For a quick start into the codebase, we have collected a couple of [reference implementations](https://github.com/stylesuxx/v3xctrl/issues?q=label%3A%22reference%22). Reviewing these commits commits will help you understand how to implement new features:

* [Trigger an action from the WebUi](https://github.com/stylesuxx/v3xctrl/issues/34)
* [Send a command from Viewer to streamer](https://github.com/stylesuxx/v3xctrl/pull/129)
* [Add a new setting to the streamer config](https://github.com/stylesuxx/v3xctrl/issues/62)
* [Add a tab to the Viewer Menu](https://github.com/stylesuxx/v3xctrl/pull/124)

## Viewer

You can develop on any OS, though **Linux is the prefered option**. Make sure you have Python Version `>=3.11.4` installed.

We recommend using `pyenv` for managing Python versions:

```bash
curl -fsSL https://pyenv.run | bash
pyenv install 3.11.9
pyenv global 3.11.9
python --version
```

Clone the repo, create a virtual environment, and install dependencies:

```bash
git clone git@github.com:stylesuxx/v3xctrl.git
cd v3xctrl
python -m venv ./venv
source ./venv/bin/activate
```

Install dependencies and run the GUI:

```bash
pip install -r ./requirements-dev.txt

cd src
python -m v3xctrl_ui.main

# Run with debug logs enabled
python -m v3xctrl_ui.main --log DEBUG
```

### Windows 11

> **NOTE:** None of the project’s developers use Windows. We cannot offer detailed support for Windows development.

Windows setup is more cumbersome and should only be used if you’re comfortable troubleshooting on your own.

Use [pyenv-win](https://github.com/pyenv-win/pyenv-win) and follow the PowerShell-based installation path (tested). You may need to allow script execution:

```Powershell
Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process
```

Then follow the same steps as above to fetch the repo, install dependencies, and run the GUI.

## Streamer

> For development, it’s strongly recommended to use the provided custom PiOS image as a starting point.

### Setup

By default the `/root` and `/` partitions are mounted **read-only**. To build or install on the Streamer, you need to temporarily switch to **read-write** mode:

```bash
sudo v3xctrl-remount rw
```

This change is persistent until you switch back to read-only mode and requires a `reboot` to take effect.

When you’re done, don’t forget to revert to read-only mode:

```bash
sudo v3xctrl-remount ro
```

### Building
You can build the `.deb` package in two ways:

1. Build on your dev machine and copy it to the Streamer (recommended: faster, less hassle)
2. Build directly on the RPi

#### Building on Dev Machine
Ensure your Streamer is in **RW mode** before installing the package.

> It is assumed you use some Debian based Linux distribution, otherwise you will have to prepare the dependencies on your own.

On your dev machine install pre-requisites:

```
sudo ./build/prepare-host.sh
```

Build deb package:

```bash
sudo ./build/build-in-chroot.sh
```

Quick build-and-copy one-liner:

```bash
sudo ./build/build-in-chroot.sh && scp ./build/tmp/dependencies/debs/v3xctrl.deb v3xctrl@v3xctrl01.local:/home/v3xctrl
```

On the Streamer, remove the old version and install the new one:

```
sudo apt remove -y --purge v3xctrl && sudo apt install ./v3xctrl.deb
```

#### Build on RPi

Install `git`, clone the repo, and run the installer script:

```bash
sudo apt update
sudo apt install git -y
git clone git@github.com:stylesuxx/v3xctrl.git
./bash/install.sh
```

After installation, you should be able to access the config web interface at:

```
http://<streamer-ip>:5000/
```


##### Update

To update the package later, you can skip setup steps and only rebuild/install:

```bash
./bash/install.sh update
```

### Custom Python

The installation provides a **custom Python environment** isolated from the system Python. It has its own interpreter and pip:

```bash
v3xctrl-python --version
v3xctrl-pip --version
```

### Modem setup

Plug in your modem. It should appear as an RNDIS network device.

Check with:

```bash
ip -c a s
```

If you don’t see the device, check the kernel log:

```bash
dmesg -c
# Plugin your device
dmesg -c
```

### Serial Console (optional but recommended)

> **Note:** Already enabled when using our custom image.

For easier debugging, enable a serial login console:

```bash
sudo raspi-config
```

Navigate to `Interface Options` -> `Serial Port` -> `Would you like a login shell to be accessible over serial?` -> `Yes` -> `OK` -> `Finish`.

Now you can connect via a USB-to-serial adapter for direct console access.

## Helper scripts

The bash directory contains **GStreamer helper scripts** for testing the video pipeline. You can use these transmitters and receivers to produce a test video stream similar to the live client stream.

## Logging

Switching from **RO** to **RW** mode also enables persistent systemd logging.

List boot logs:

```bash
journalctl --list-boots
```

To view the boot log of a specific boot:

```bash
journalctl -b $BOOT_ID --no-pager
journalctl -b 0 --no-pager   # Current
journalctl -b -1 --no-pager  # Previous boot

```

## Tests

Run tests:

```bash
# All
python -m pytest tests

# Just ui
python -m pytest tests/v3xctrl-ui

# Just server
python -m pytest tests/v3xctrl_control
```

Automatically re-run tests on file changes:

```bash
python watch_tests.py
```

Run tests with coverage and show missing lines:

```bash
python -m pytest --cov=v3xctrl_ui.menu.TextInput --cov-report=term-missing tests/v3xctrl_ui/menu/test_TextInput.py
```
