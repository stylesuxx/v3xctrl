# V3XCTRL - /vɛks kənˈtɹoʊl/ (Video eXchange and ConTRoL)

> Control your vehicle and stream video over 4G from anywhere.

This project provides a platform to stream video and control servos via a 4G mobile connection using low cost, off the shelf hardware with minimal latency.

The documentation is split into multiple files:

- [Terminology](https://github.com/stylesuxx/v3xctrl/wiki/Terminology) - read this to understand the terminology of the project
- [Recommended Hardware](https://github.com/stylesuxx/v3xctrl/wiki/Hardware) - Which hardware you are going to need
- [Streamer Setup](v/stylesuxx/v3xctrl/wiki/Streamer) - How to set up your hardware (the streamer)
- [Motivation](https://github.com/stylesuxx/v3xctrl/wiki/Motivation) - If you want to understand why things are implemented as they are, this document should help you
- [Troubleshooting](https://github.com/stylesuxx/v3xctrl/wiki/Troubleshooting) - read this before opening issues, your problem might have already been solved
- [Latency Breakdown](https://github.com/stylesuxx/v3xctrl/wiki/Latency) - how much latency is there and where does it come from?

## Support

If you need any help feel free to open an [issue here](https://github.com/stylesuxx/v3xctrl/issues), or even better, join us on [Discord](https://discord.gg/uF4hf8UBBW).

## Quickstart

This section is meant to get you up and running within minutes.

> In this quickstart guide, we assume that the login user is `pi` and the streamers host name has been set to `v3xctrl` - substitute those to the values you used during streamer setup.

> Make sure the modem is attached but do not insert your SIM card yet.

### Prerequisites

- A Raspberry Pi Zero 2W
- A SD card (good quality, at least 8GB - if you want to save videos, bigger is better)
- A compatible 4G modem
- A Raspberry Pi Zero 2W compatible camera
- Electronic speed controller - ESC (with PWM input)
- Servo (with PWM input)

> Check [Recommended Hardware](https://github.com/stylesuxx/v3xctrl/wiki/Hardware) for a list of compatible modems and cameras.

### Viewer Configuration

Let's first prepare the viewer - this is where the video feed will be displayed and your inputs connect to.

Download, extract and run the GUI for your operating system:

* [Linux](/releases/latest/GUI_Linux.zip)
* [Windows](/releases/latest/GUI_Windows.zip)
* [MacOS](/releases/latest/GUI_MacOS.zip)

On the computer running the viewer, make sure the following ports are open (you might need to forward them through your router):

- `6666`: UDP for receiving video (UDP & TCP for running self-tests)
- `6668`: UDP for receiving UDP messages

#### No static IP or mobile network

If the computer you are running the viewer on does not have a static IP address or you are on a mobile network, you will have to use the UDP Relay instead of configuring port forwarding.

After starting the GUI, enter the Menu and check the *"Enable UDP Relay"* checkbox. If you are using the default server, a valid ID has to be requested in our [Discord](https://discord.gg/uF4hf8UBBW).

> **NOTE**: This mode is a bit more difficult for initial configuration, so if at all possible, use the direct connection instead.

### Streamer

Make sure to follow the [Streamer setup guide](https://github.com/stylesuxx/v3xctrl/wiki/Streamer#installation-recommended).

Once the image is flashed an you have verified you can connect to the streamers web interface under `http://v3xctrl.local:5000` follow the next steps:

* Set the host field, to your viewers IP address
* In the *"Video"* section, make sure that the *"Test Image"* is enabled

> If you enabled the UDP relay in the previous step, make sure that you enter your *"Relay session ID"* and select *"relay"* in the *"Connection Mode"* dropdown.

Click "Save".

#### Testing video stream

Switch to the *"Services"* tab and start the `v3xctrl-video` service, the service status should change from `inactive` to `active`.

After a couple of seconds you should see a video feed in the viewer.

> Should this not be the case, follow the [Troubleshooting Guide](https://github.com/stylesuxx/v3xctrl/wiki/Troubleshooting#video-stream).

##### Testing video transmission with camera

Now that we have verified that video streaming is working, we want to make sure that the camera is working too.

In the *"Config Editor"* tab, uncheck the *"Test Video"* checkbox in the video section and restart the video stream from the *"Services"* tab (stop and then start again).

After a couple of seconds you should see the live camera feed in the **viewer**.

> Should this not be the case, follow the [Troubleshooting Guide](https://github.com/stylesuxx/v3xctrl/wiki/Troubleshooting#video-stream).

#### Calibration
Calibration is done through the *"Calibration"* tab, make sure the `control` service is inactive, otherwise calibration will not work.

Make sure servo and speed-controller are attached to your RPi Zero 2W. By default the following GPIO pins are used for PWM:

* `18`: Throttle
* `13`: Steering

##### Steering
Steering calibration is quite straight forward, adjust min and max value according to your servo.

Decrease the min value until your preferred position is reached or until the servo starts making noises (that is a sign that you went to far) and dial the range back a bit.

Do the same for the max value, just increasing instead of decreasing the value.

Make sure to adjust trim such that the servo is centered. You will most likely have to fine tune this value during operation, but you should be able to make decent raw adjustments at this point.

##### Throttle
**IMPORTANT:** Make sure you read the manual for your ESC, calibration for throttle differs from manufacturer to manufacturer. Most likely you will not have to change, min, max and idle values. Instead you will have to send min, idle and max values in a specific order.

#### Testing control

After calibration you can use `w`, `s`, `a`, `d` in the viewer to verify movement. If steering is inverted, you can adjust it on your streamer in the *"Config editor"* tab under *"Controls" -> "Steering" -> "Invert Steering"*.

At this point you can also go ahead and calibrate the input device of your choice.

#### Auto start video stream & control

After you have verified in the above steps, that the video stream and control channel are working as expected, you can enable auto starting them on boot-up:

In the web-interface, check `video` and `control` in the *"Autostart"* section of the *"Config editor"* and hit "Save".

> Be aware that from this point forward, the video stream will be transmitted after boot-up, so after the next step, you will use mobile data once the streamer has started.

#### Testing SIM card

Follow the steps in the [SIM card documentation](https://github.com/stylesuxx/v3xctrl/wiki/SIM). To prepare your SIM card. After you have made sure, that the SIM card is usable, insert it into the streamer, switch to the *"Modem"* tab and make sure that the modem is connecting to the carrier network. Make sure that the following points are true:

* *"SIM Status"* shows `OK`
* *"Carrier"* is **not** `0`
* *"Context 1"* is set to `IP xxx.xxx.xxx.xxx (yyy)`

If those above points are true, then you are ready to stream over your mobile network.

#### Force data over modem

In the *"Config Editor"* tab, navigate the *"Network" -> "WiFi"* and set *"routing"* to `rndis`.

After this, hit *"Reboot"* on top of the menu and after about a minute, the streamer should be rebooted and re-connected to the viewer.

> Congratulations, you are good to go. Have fun!

## Support

If you have any questions or problems, feel free to open an issue. Please make sure to check the [Troubleshooting Guide](https://github.com/stylesuxx/v3xctrl/wiki/Troubleshooting) first, your problem might have already been solved.

## Development

Check the following documentation if you are interested in contributing to the project:

- [Development](https://github.com/stylesuxx/v3xctrl/wiki/Development) - how to setup your development environment
- [Release](https://github.com/stylesuxx/v3xctrl/wiki/Release) - how to release a new version of the project

### Contributing

PR's are welcome, please direct them against the develop branch. Before investing a lot of time into a new feature, feel free to discuss with us beforehand, we might have some pointers for you.

Feel free to open issues if you have any questions, problems or suggestions.
