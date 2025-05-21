# Web Interface
After installation on the client there will be a web interface available at `http://192.168.1.89:5000/` - change the IP to the IP of your client.

## Configuration
The configuration should be pretty self-explanatory. The one setting you will have to change is the host.

> Please be aware that a reboot is required after changing the configuration.

### WiFi
WiFi can either be run in client or in AP mode. In client mode it will try to connect to the network configured when you initially flashed the image. In AP mode, it will spawn it's own WiFi network to which you can connect to.

The default AP network is `v3xctrl-<device_id>`.
The default password is `raspberry`.

I suggest to keep the device in client mode as long as you are setting it up and then switch it to AP mode when you are done. This will allow you to connect to the device on the field via your phone.