# V3XCTRL - /vɛks kənˈtɹoʊl/ (Video eXchange and ConTRoL)

> Control your vehicle and stream video over 4G from anywhere.

This project provides a platform to stream video and control servos via a 4G mobile connection using low cost, off the shelf hardware with minimal latency.

The documentation is split into multiple files:

- [Terminology](/master/docs/Terminology.md) - read this to understand the terminology of the project
- [Recommended Hardware](/master/docs/Hardware.md) - Which hardware you are going to need
- [Client Setup](/master/docs/Client.md) - How to set up your hardware (the client)
- [Motivation](/master/docs/Motivation.md) - If you want to understand why things are implemented as they are, this document should help you
- [Troubleshooting](/master/docs/Troubleshooting.md) - read this before opening issues, your problem might have already been solved
- [Latency Breakdown](/master/docs/Latency.md) - how much latency is there and where does it come from?

## Support

If you need any help feel free to open an [issue here](https://github.com/stylesuxx/v3xctrl/issues), or even better, join us on [Discord](https://discord.gg/uF4hf8UBBW).

## Quickstart

This section is meant to get you up and running within minutes.

> In this quickstart guide, we assume that the login user is `pi` and the clients host name has been set to `v3xctrl` - substitute those to the values you used during client setup.

> Do not attach the modem yet, first run through the setup and attach the modem in the last step. This will help you in debugging, should some issues arise.

### Prerequisites

- A Raspberry Pi Zero 2 W
- A SD card (good quality, at least 8GB - if you want to save videos, bigger is better)
- A 4G modem
- Electronic speed controller - ESC (with PWM input)
- Servo (with PWM input)

### Server Configuration

On the server, make sure the following ports are open (you might need to forward them through your router) on your Server:

- `6666`: UDP for receiving video (UDP & TCP for running self-tests)
- `6668`: UDP for receiving UDP messages

Download, extract and run the GUI for your operating system:

* [Linux](/releases/latest/GUI_Linux.zip)
* [Windows](/releases/latest/GUI_Windows.zip)
* [MacOS](/releases/latest/GUI_MacOS.zip)

### Client

Make sure to follow the [client setup guide](/master/docs/Client.md#installation-recommended) in the Client.

Once the image is flashed an you have verified you can connect to the clients web server under: `http://v3xctrl.local:5000`

* Set the host field, to your servers IP address
* In the "video" section, make sure that the "testSource" is enabled

Click "Save".

#### Testing video stream

Connect via SSH to the client and start the video service:

```bash
ssh pi@v3xctrl.local
sudo systemctl start rc-video
```

After a couple of seconds you should see a video feed in the server GUI. Should this not be the case, follow the [Troubleshooting Guide](/master/docs/Troubleshooting.md#video-stream).

##### Testing video transmission with camera

Now that we have verified that video streaming is working, we want to make sure that the camera is working too.

In the web-interface, uncheck the "testSource" checkbox in the video section and restart the video stream via command line:

```bash
sudo systemctl restart rc-video
```

After a couple of seconds you should see the live camera feed in the server GUI. Should this not be the case, follow the [Troubleshooting Guide](/master/docs/Troubleshooting.md#video-stream).


#### Testing control

The easiest way to test the control channel is to attach a servo (since it does not need calibration in contrary to an ESC).

By default the following GPIO pins are used for PWM:

* `18`: Throttle
* `13`: Steering

Start the control service:

```bash
sudo systemctl start rc-control
```

#### Calibration

##### Steering
Steering calibration is quite straight forward, adjust min and max value according to your servo.

Decrease the min value until your preferred position is reached or until the servo starts making noises (that is a sign that you went to far) and dial the range back a bit.

Do the same for the max value, just increasing instead of decreasing the value.

Make sure to adjust trim such that the servo is centered. You will most likely have to fine tune this value during operation, but you should be able to make raw adjustments at this point.

##### Throttle
**IMPORTANT:** Make sure you read the manual for your ESC, calibration for throttle differs from manufacturer to manufacturer. Most likely you will not have to change, min, max and idle values. Instead you will have to send min, idle and max values in a specific order.

#### Auto start video stream & control

After you have verified, that the video stream and control channel are working as expected, you can enable auto starting them on bootup:

In the web-interface, check "video" and "control" in the "Autostart" section and hit "Save".


#### Force data over modem

After verifying that two way communication works, it is time to attach the modem and force the whole traffic over it.

Attach the modem and verify that it is picked up by the operating system:

```bash
ip a s
```

You should now see a device named `eth0` or `usb0` - if you only see `lo` and `wlan0`, than your modem is not being picked up - check the [troubleshooting guide](/master/docs/Troubleshooting.md#modem).

In the web-interface, force all traffic to go through this RNDIS device:

* In the WiFi section set routing to `rndis`

Hit "Save" and reboot the device:

```bash
sudo reboot
```

## Support

If you have any questions or problems, feel free to open an issue. Please make sure to check the [Troubleshooting Guide](/master/docs/Troubleshooting.md) first, your problem might have already been solved.

## Development

Check the following documentation if you are interested in contributing to the project:

- [Development](/master/docs/Development.md) - how to setup your development environment
- [Release](/master/docs/Release.md) - how to release a new version of the project

### Contributing

PR's are welcome, please direct them against the develop branch. Feel free to open issues if you have any questions or problems.
