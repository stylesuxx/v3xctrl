# Client

The client is the heart of the project: Transmitting video, receiving control commands, and managing the actuators.

## Installation (recommended)

We provide a PiOS based - ready to flash - image. Just [download the image](/releases/latest/v3xctrl-raspios.img.xz) and flash it to your SD card using the [Raspberry Pi Imager Utility](https://www.raspberrypi.com/news/raspberry-pi-imager-imaging-utility/).

When Imager asks you to apply OS customization settings, select "Edit Settings" and set up the following:

General tab
* Set hostname to something unique in your network, e.g.: `v3xctrl`
* Set username and password - if you don't set this, the defaults will be applied, e.g.: `pi` and `raspberry`
* Configure wireless LAN - set SSID and password of your home network

Services tab
* Enable SSH
* Enable "public-key authentication only" (optional, but recommended)

Then "Save" and "Yes" to apply the settings.

### Verification

> Do not attach your 4G modem yet, we want to make sure that everything is working through your internal network first.

Once done, insert the SD card into your RPI and power up - it will take a while, but after about a minute you should be able to connect via SSH using your user and hostname:

```bash
ssh pi@v3xctrl.local
```

If you can connect, you are ready for the next step of the configuration.

If you can not connect, check the [trouble shooting section](/master/docs/Troubleshooting.md#ssh-connection)

## Installation (for development)

> Even for development, it's recommended to use the provided, custom PiOS image and go from there.

There is an install script in place which will help you to get your dev environment going.

Install `git`, clone the repository and run the installer:

```bash
sudo apt update
sudo apt install git -y
git clone git@github.com:stylesuxx/rc-stream.git
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

This will re-build the rc-client package and install it over the already installed one.

## Services

After installation there will be a few services available, some of them enabled by default. `systemd` is used for service management and all the services can be controlled by it:

```bash
# See the status of a service
systemctl status rc-config-server

# Restart a service
systemctl restart rc-config-server

# See the last 50 lines of a service log
journalctl -u rc-config-server -n50
```

> NOTE: Always start the services through `systemd`, this will assure that they will run with the correct users and permissions.

### rc-config-server (enabled by default)
This service is responsible for the confiugration web interface. It is running on port 5000 by default and can be accessed via `http://$CLIENT_IP:5000/`.

### rc-wifi-mode (enabled by default)
This service checks your wifi config on startup and starts your WiFi device in **client** or **access point** mode.

### rc-service-manager (enabled by default)
This service starts services on startup according to the configuration.

### rc-video
This service is responsible for sending the video feed to the server.

> This service is not meant to be enabled. It is started by the `rc-service-manager` service if autostart is enabled in the config.

### rc-control
This service is responsible for the control connection between client and server and is ultimately what controls the actuators.

> This service is not meant to be enabled. It is started by the `rc-service-manager` service if autostart is enabled in the config.
