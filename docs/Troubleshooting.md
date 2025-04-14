# Troubleshooting

If you encounter any issues, this document will help you troubleshoot and resolve them.

## SSH connection
If after installation and first boot, you can not connect via SSH, check the following:

- Make sure your client gets assigned an IP address by your router
- Make sure you are using the correct hostname
- Try connecting to IP directly instead of using the hostname

### No IP assigned
If on the router you can not see your client in the list of connected devices, it is very likely that you did not set your WiFi credentials correctly when flashing the image. Double check the settings and flash the image again.

## Config Server
The webserver for configuration is started by default after installing the package.

### Can not connect
The webserver is by default running on port `5000` and can be accessed via `http://$CLIENT_IP:5000/`. If the client is in Access Point mode, you will be able to connect via `http://192.168.23.1:5000`.

If you can not connect to the webserver, check the following:

- Make sure you are using the correct IP address - check your router
- Make sure the webserver is running: `systemctl status rc-config-server`
- If it is not running, enable it and start:

```bash
sudo systemctl enable rc-config-server
sudo systemctl start rc-config-server
```

- If status is failed, check the logs: `journalctl -u rc-config-server -n 50`

## Video stream

### Not receiving video stream
- Check the config server, have a look at the vide port, by default this is `6666`
- Make sure the port is forwarded on your router to your server (consult the manual for your router to find out how to do this - usually this will be in a section called "port forwarding" or "NAT")

If you made sure that the port is forwarded correctly and still not receiving the video stream, try the following:

- Check the status of the `rc-video` service: `systemctl status rc-video` - this service is not started automatically unless you enable it to be autostarted in the config.
- Try to start it manually: `sudo systemctl start rc-video`

If there is still no video stream:
- Check the logs of the `rc-video` service: `journalctl -u rc-video -n 50` - this will give you more information about what is going on with the service.

Often times an issue can be a bad connection with the camera. To rule out the camera as an error source you can enable `testSource` in the `video` config section, this will send a test pattern instead of the camera feed to the client.

If you can see the test pattern, double check your camera connection.

### Stream very laggy
Lag should not be an issue - we are dropping frames if they can not be sent fast enough on the client or if the encoder can not process them fast enough.

Monitor the FPS on the server - if the Main `Loop` does not run at the full framerate of 60FPS, it is an indicator that your server is not capable of handling the load.

### Drop in Video frames
If the `Video` FPS counter does not show the configured FPS (30 per defautlt), there could be multiple reasons for this:

1. If the main `Loop` also is not running at full (60 by default) FPS, then your server machine is the issue.
2. If the main `Loop` is running at full FPS, but the `Video` loop is dropping, then this is most likely an issue with the network connection. Run the self check tests. The default video is set to 1.8Mbps, if your connection tests slower than that, then you need to adjust the bitrate accordingly. Tests have shown that a bitrate of 1Mbps is still usable.

> As a reference, with a Cat 1, 4G modem your maximum upload speed will be 5Mbps. Benchmarks have shown that more realistically your upload will be at around 3.5Mbps on average. But this depends a lot on your provider and the coverage in your area.

### A lot of blocking/artifacts
We are using h264 encoded video. This format uses reference frames (I frames) and the following frames are encoded based on the reference frames. If the reference frame is not received, then the following frames will be displayed wrongly and it might result in blocking/artifacting.

In this case you will also see a drop in vide framerate - use the same steps to mitigate the issue as described above.

You can also try to decrease the `iFramePeriod` in the `video` config section. This will increase the number of I frames and thus reduce the blocking/artifacting.
