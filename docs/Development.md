# Development

This document aims in helping you get your development environment set up for both the server and client.

> If you are just a regular user, you can skip this section.

## Server (GUI)

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
python -m ui.main

# Run with debug logs enabled
python -m ui.main --log DEBUG
```

### Windows 11

> Please do not ask for support on how to develop on Windows. Non of the projects devs use Windows, we can't (don't want to) help you with that.

Dev setup under Windows 11 is a bit more complicated and should only be used if you really hate yourself.

Use [pyenv-win](https://github.com/pyenv-win/pyenv-win) to get your python venv going - use the setup via `PowerShell` (this is the tested path).

> In PowerShell you might need to run `Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process` for windows to not complain about permissions.

Follow the steps from above to fetch the repo, install dependencies and start the GUI.

## Client

> Even for development, it's recommended to use the provided, custom PiOS image and go from there.

### Setup

By default th `/root` and `/` partitions are mounted read-only. In order to be able to build on the client itself, you need to switch to read-write mode:

```bash
sudo v3xctrl-remount rw
```

This will switch the partitions to read-write mode and disable the overlay fs. This is persistent, until you switch back to read-only mode and requires a `reboot` to take effect.

Do not forget to switch back to read-only mode when done:

```bash
sudo v3xctrl-remount ro
```

### Install

There is an install script in place which will help you to get your dev environment going.

Install `git`, clone the repository and run the installer:

```bash
sudo apt update
sudo apt install git -y
git clone git@github.com:stylesuxx/v3xctrl.git
./bash/install.sh
```

You should now be able to access the config web interface at `http://192.168.1.89:5000/` - change the IP to the IP of your client.


### Update

To update the client package you again run the install script, but you can omit all the steps apart from building and installing the package.

```bash
./bash/install.sh update
```

### Custom Python

During installation a custom python version is installed. It is isolated from the system python and uses it's own environment.

It has it's own interpreter and pip:

```bash
rc-python --version
rc-pip --version
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

#### Routeing traffic

We want to make sure that all internal traffic is routed through the wifi adapter. All external traffic should go through the 4G modem.

> This assumes you use the default dhcpcd and not NetworkManager!

Open `/etc/dhcpcd.conf` and add:

```text
interface wlan0
    nogateway
```

Edit `/etc/dhcpcd.exit-hook`:

```text
if [ "$interface" = "wlan0" ]; then
    subnet=$(ip -4 addr show wlan0 | awk '/inet/ {print $2}')
    ip route add "$subnet" dev wlan0
fi
```

and make it executable:

```bash
sudo chmod +x /etc/dhcpcd.exit-hook
```

Now reboot and make sure that the rules are applied:

```bash
ip route show
```

Use `mtr` to verify the correct device is being used for routing your traffic:

```bash
mtr 192.168.1.1
mtr google.com
```

When running each of them, you should see different IP addresses on top indicating which device is being used for routing.

### Serial Console (optional but recommended)

> **Note:** This is already enabled when using our custom image.

You might want to enable debugging/login on the serial console. This will allow you an easy debugging port in case something goes wrong.

```bash
sudo raspi-config
```

Navigate to `Interface Options` -> `Serial Port` -> `Would you like a login shell to be accessible over serial?` -> `Yes` -> `OK` -> `Finish`.

Now you will be able to access the serial console via USB to serial adapter

### Update

If you are running the dev env and you just want to update your client, you can simply run the installer again passing the update Parameter:

```bash
./install.sh update
```

This will re-build the `v3xctrl` package and install it over the already installed one.


## Helper scripts

The bash script directory contains `gstreamer` related functionality. You will find two scripts to help you verify/test your video pipeline, they are gstreamer based transmitters and receivers. You can use them during development to produce a video stream close to what the client sends.

## Tests

Run tests:

```bash
# All
python -m pytest tests

# Just ui
python -m pytest tests/ui

# Just server
python -m pytest tests/rpi_4g_streamer
```

Watch for file changes and re-run tests automatically:

```bash
python watch_tests.py
```