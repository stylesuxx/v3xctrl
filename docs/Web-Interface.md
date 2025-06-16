# Web Interface
After installation on the streamer there will be a web interface available at `http://192.168.1.89:5000/` - change the IP to the IP of your streamer.

## Config Editor
The `Config Editor` should be pretty self-explanatory. The one setting you will have to change is the host.

> Please be aware that a reboot is required after changing the configuration.

### Network
#### Ports
Here you can change the default ports for the web interface and the services. You really only need to change those settings if you are running other services on the same pi which **need** those ports.

> Generally, this section can be left alone.

#### WiFi
WiFi can either be run in client or in AP mode. In client mode it will try to connect to the network configured when you initially flashed the image. In AP mode, it will spawn it's own WiFi network to which you can connect to.

The default AP network is `v3xctrl-<device_id>`.
The default password is `raspberry`.

I suggest to keep the device in client mode as long as you are setting it up and then switch it to AP mode when you are done. This will allow you to connect to the device on the field via your phone.

#### Modem
The most important section here are the Bands. You might need to adjust the bands for your region. Best use cellmapper to find out which bands are available in your region for your provider.

> We also noted that the modem seems to prefer the higher frequency, higher throughput bands, which might not be the best choice in rural regions. We found out, that pinning the modem to a single band might yield WAY better results. In rural regions with not so great coverage that would be the lower frequency bands (Band 20 in the EU for example).

## Services
Allows you to manage all relevant services. You can see their current states, start and stop them and see their logs.

## Calibration
Allows you to calibrate steering and throttle.

## DMESG
Shows the kernel logs of the current session, very important for debugging.

## Modem
Shows information about the modem.
