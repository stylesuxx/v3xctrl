# Troubleshooting

If you encounter any issues, this document will help you troubleshoot and resolve them.

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

- If status is failed, check the logs: `journalctl -u rc-config-server -n 100`

## Video stream

### Not receiving video stream
- Check the config server, have a look at the vide port, by default this is `6666`
- Make sure the port is forwarded on your router to your server (consult the manual for your router to find out how to do this - usually this will be in a section called "port forwarding" or "NAT")

If you made sure that the port is forwarded correctly and still not receiving the video stream, try the following:

- Check the status of the `rc-transmit-camera` service: `systemctl status rc-transmit-camera` - this service is not started automatically unless you enable it to be autostarted in the config.
- Try to start it manually: `sudo systemctl start rc-transmit-camera`

If there is still no video stream:
- Check the logs of the `rc-transmit-camera` service: `journalctl -u rc-transmit-camera -n 100` - this will give you more information about what is going on with the service.

Often times an issue can be a bad connection with the camera. To rule out the camera as an error source you can enable `testSource` in the `video` config section, this will send a test pattern instead of the camera feed to the client.

If you can see the test pattern, double check your camera connection.
