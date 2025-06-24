# Streamer

The streamer is the heart of the project: Transmitting video, receiving control commands, and managing the actuators.

## Installation (recommended)

We provide a PiOS based - ready to flash - image. Just [download the image](/releases/latest/v3xctrl-raspios.img.xz) and flash it to your SD card using the [Raspberry Pi Imager Utility](https://www.raspberrypi.com/news/raspberry-pi-imager-imaging-utility/).

When Imager asks you to apply OS customization settings, select "Edit Settings" and set up the following:

General tab
* Set hostname to something unique in your network, e.g.: `v3xctrl`
* Set username and password - if you don't set this, the defaults will be applied, e.g.: `pi` and `raspberry`
* Configure wireless LAN - set SSID and password of your home network
* Set regulatory domain to your country (if you simply care for max TX power, set to US)

Services tab
* Enable SSH
* Enable "public-key authentication only" (optional, but recommended)

Then "Save" and "Yes" to apply the settings.

### Verification

> Do not attach your 4G modem yet, we want to make sure that everything is working through your internal network first.

Once done, insert the SD card into your RPI and power up - it will take a while, but after about two and a half minutes you should be able to connect via SSH using your user and hostname:

```bash
ssh pi@v3xctrl.local
```

If you can connect, you are ready for the next step of the configuration.

> Be aware that only the first boot will take longer, afterwards you should be able to connect via SSH after about 30 seconds from plugging in the streamer.

If you can not connect, check the [trouble shooting section](/master/docs/Troubleshooting.md#ssh-connection)

## Services

After installation there will be a few services available, some of them enabled by default. `systemd` is used for service management and all the services can be controlled by it:

```bash
# See the status of a service
systemctl status v3xctrl-config-server

# Restart a service
systemctl restart v3xctrl-config-server

# See the last 50 lines of a service log
journalctl -u v3xctrl-config-server -n50
```

> NOTE: Always start the services through `systemd`, this will assure that they will run with the correct users and permissions.

### v3xctrl-config-server (enabled by default)

This service is responsible for the confiugration web interface. It is running on port 5000 by default and can be accessed via `http://v3xctrl.local:5000/`.

### v3xctrl-wifi-mode (enabled by default)

This service checks your wifi config on startup and starts your WiFi device in **client** or **access point** mode.

### v3xctrl-service-manager (enabled by default)

This service starts services on startup according to the configuration.

### v3xctrl-cleanup (enabled by default)

This service is responsible for cleaning up fragments of a previous unclean shutdown.

### v3xctrl-video

This service is responsible for sending the video feed to the viewer.

> This service is not meant to be enabled. It is started by the `v3xctrl-service-manager` service if autostart is enabled in the config.

### v3xctrl-control

This service is responsible for the control connection between streamer and viewer and is ultimately what controls the actuators.

> This service is not meant to be enabled. It is started by the `v3xctrl-service-manager` service if autostart is enabled in the config.

### SAMBA share

There is a samba share for the recordings directory. You can access it via `smb://v3xctrl.local/recordings`. Use the username and password are both `v3xctrl`.

Samba is not enabled by default, you need to enable it in the config in the `Extras` section.
