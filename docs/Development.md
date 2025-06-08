# Development

This document aims in helping you get your development environment set up for both - streamer and viewer.

> If you are just a regular user, you can skip this section.

## Reference Implementations

For a quick entry into the codebase, we have collected a couple of [reference implementations](https://github.com/stylesuxx/v3xctrl/issues?q=label%3A%22reference%22). Following those commits, you should quickly get a feel for how to implement a feature you are looking for:

* [Trigger an action from the WebUi](https://github.com/stylesuxx/v3xctrl/issues/34)
* [Send a command from Viewer to streamer](https://github.com/stylesuxx/v3xctrl/issues/54)
* [Add a new setting to the streamer config](https://github.com/stylesuxx/v3xctrl/issues/62)
* [Add a tab to the Viewer Menu](https://github.com/stylesuxx/v3xctrl/issues/91)

## Viewer

You can develop on any OS - Linux is the prefered method though. Make sure Python Version `>=3.11.4` is installed.

The most comfortable way is to do this via `pyenv`:

```bash
curl -fsSL https://pyenv.run | bash
pyenv install 3.11.9
pyenv global 3.11.9
python --version
```

Then clone the repo, create a `venv` and install dependencies:

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

> Please do not ask for support on how to develop on Windows. Non of the projects devs use Windows, we can't (don't want to) help you with that.

Dev setup under Windows 11 is a bit more complicated and should only be used if you really hate yourself.

Use [pyenv-win](https://github.com/pyenv-win/pyenv-win) to get your python venv going - use the setup via `PowerShell` (this is the tested path).

> In PowerShell you might need to run `Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process` for windows to not complain about permissions.

Follow the steps from above to fetch the repo, install dependencies and start the GUI.

## Streamer

> Even for development, it's recommended to use the provided, custom PiOS image and go from there.

### Setup

By default th `/root` and `/` partitions are mounted read-only. In order to be able to build/install on the streamer, you need to switch to read-write mode:

```bash
sudo v3xctrl-remount rw
```

This will switch the partitions to read-write mode and disable the overlay fs. This is persistent, until you switch back to read-only mode and requires a `reboot` to take effect.

Do not forget to switch back to read-only mode when done:

```bash
sudo v3xctrl-remount ro
```

### Building
To build the deb package you have two options:

1. Build on your dev machine, move the package over and install
2. Build on RPi itself

The preferred method, faster and less hassle is to build on the dev machine:

#### Building on dev machine
For this method to work, make sure you are in RW mode on the streamer.

On the dev machine install pre-requisites:

```
sudo ./build/prepare-host.sh
```

Build deb package:

```bash
sudo ./build/build-in-chroot.sh
```

A convenient one-liner to build and move to streamer:

```bash
sudo ./build/build-in-chroot.sh && scp ./build/tmp/dependencies/debs/v3xctrl.deb v3xctrl@v3xctrl01.local:/home/v3xctrl
```

Then on the streamer simply remove old version and install new one:

```
sudo apt remove -y --purge v3xctrl && sudo apt install ./v3xctrl.deb
```

#### Building on Rpi

There is an install script in place which will help you to get your dev environment going.

Install `git`, clone the repository and run the installer:

```bash
sudo apt update
sudo apt install git -y
git clone git@github.com:stylesuxx/v3xctrl.git
./bash/install.sh
```

You should now be able to access the config web interface at `http://192.168.1.89:5000/` - change the IP to the IP of your client.


##### Update

To update the client package you again run the install script, but you can omit all the steps apart from building and installing the package.

```bash
./bash/install.sh update
```

### Custom Python

During installation a custom python version is installed. It is isolated from the system python and uses it's own environment.

It has it's own interpreter and pip:

```bash
v3xctrl-python --version
v3xctrl-pip --version
```

### Modem setup

Plug in your modem, it should be recognizes as a RNDIS network device.

Check with:

```bash
ip -c a s
```

Should you not see the device here, check with `dmesg` what's going on:

```bash
dmesg -c
# Plugin your device
dmesg -c
```

### Serial Console (optional but recommended)

> **Note:** This is already enabled when using our custom image.

You might want to enable debugging/login on the serial console. This will allow you an easy debugging port in case something goes wrong.

```bash
sudo raspi-config
```

Navigate to `Interface Options` -> `Serial Port` -> `Would you like a login shell to be accessible over serial?` -> `Yes` -> `OK` -> `Finish`.

Now you will be able to access the serial console via USB to serial adapter

## Helper scripts

The bash script directory contains `gstreamer` related functionality. You will find two scripts to help you verify/test your video pipeline, they are gstreamer based transmitters and receivers. You can use them during development to produce a video stream close to what the client sends.

## Logging

When switching from RO to RW mode, persistent systemd logging is enabled. To show a list of available boot logs:

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

Watch for file changes and re-run tests automatically:

```bash
python watch_tests.py
```

Run tests with coverage, show missing:

```bash
python -m pytest --cov=v3xctrl_ui.menu.TextInput --cov-report=term-missing tests/v3xctrl_ui/menu/test_TextInput.py
```
