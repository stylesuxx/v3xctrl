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

## Installation
There is an install script in place which will help you to get most of the setup done for you.

Install `git`, clone the repository and run the installer:

```bash
sudo apt update
sudo apt install git -y
git clone git@github.com:stylesuxx/rc-stream.git
cd rc-stream/bash
sudo ./install.sh
```

You should now be able to access the config web interface at `http://192.168.1.89:5000/` - change the IP to the IP of your client.

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

## Update
If you are running the dev env and you just want to update your client, you can simply run the installer again passing the update Parameter:

```bash
sudo ./install.sh update
```

This will re-build the rc-client package and install it over the already installed one.
