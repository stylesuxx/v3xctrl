# Client
There are multiple hardware platforms that can be used as clients. We decided to go with a 'Raspberry Pi Zero 2 W' for this project.

The 'Raspberry Pi Zero 2 W' has most of what we need:
* small size
* widely available
* hardware video encoder
* dedicated camera platform
* USB
* Wifi
* 2x Hardware PWM (with 500MHz clock - use pigpio)
* GPIO

The 'RPi Zero 2 W' has no issues encoding video streams in realtime in 1920x1080@30fps. This will only be feasible with higher category 4G modems but obviously lower resolution won't be an issue either.

## Hardware
The client will be interacting with different sensor and actuators. This is a selection of some useful things to consider:

Sensors:
* INA219 for measuring battery voltage
* GPS ()

Actuators:
* Speedcontroller (PWM based) - preferably with BEC to supply Servo(s) with power
* Servo(s) (PWM based)

Power supply:
* Step down converter to provide stable 5V@3A

Modem:
* 4G Modem - as long as it provides a rndis device, any is fine - as mentioned above, higher category is preferred.

## Software
As base we decided to use PiOS. Unfortunately, Bookworm seems to have some issues with the RNDIS modem, so we went with Bullseye Lite 64Bit (Listed as legacy in th PI Imager utility).

But generally speaking, the exact distribution should not matter too much. We will be using Python for most things and `gstreamer` for the rest.

When preparing your SD card, use the [Raspberry Pi Imager Utility](https://www.raspberrypi.com/news/raspberry-pi-imager-imaging-utility/) and configure it to connect to your Wifi.

> Do not attach your 4G modem yet, let's first get the biggest chunk downloaded through your regular internet.

## Serial Console
You might want to enable debugging/login on the serial console. This will allow you an easy debugging port in case something goes wrong.

```bash
sudo raspi-config
```

Navigate to `Interface Options` -> `Serial Port` -> `Would you like a login shell to be accessible over serial?` -> `Yes` -> `OK` -> `Finish`.

Now you will be able to access the serial console via USB to serial adapter

### SWAP
You will need to increase your SWAP file, as the Raspberry Pi Zero 2 W has only 512MB of RAM - I used 8GB for this but you can re-size it back after installing all dependencies.

```bash
sudo dphys-swapfile swapoff
```

```bash
sudo nano /etc/dphys-swapfile
```
adjust the parameters like so (they should already be in the file, just with different sizes):

```
CONF_SWAPSIZE=8192
CONF_MAXSWAP=8192
```

```bash
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

You can now use `htop` to verify that the swap size has been changed accordingly.

> After installing python, you can safely revert the Swap again to its original size.

## Dependencies
Upgrade and install dependencies:

```bash
sudo apt update
sudo apt upgrade
sudo apt install git libssl-dev gstreamer1.0-plugins-bad gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly gstreamer1.0-tools libbz2-dev libsqlite3-dev libcamera-apps libcamera-dev libcamera-tools tcpdump liblzma-dev libreadline-dev libctypes-ocaml-dev libcurses-ocaml-dev libffi-dev mtr screen
```

### Fixing locale
Most likely you will need to fix the locale:

```bash
sudo dpkg-reconfigure locales
```

Select `en_US.UTF-8 UTF-8` (or whichever you w ant to use).

### Python
Install pyenv for easy python version management, follow the setup hints, install python and verify the version:

```bash
curl -fsSL https://pyenv.run | bash
pyenv install 3.11.4
pyenv global 3.11.4
python --version
```

### Get code
Clone the repository and create venv:

```bash
git clone git@github.com:stylesuxx/rc-stream.git
cd rc-stream
python -m venv .
source bin/activate
pip install -r requirements.txt
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
```

you should see the IP address of your wifi device on top.


```bash
mtr google.com
```

This should show you the IP address of your 4G modem on top.
