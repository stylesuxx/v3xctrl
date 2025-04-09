# Troubleshooting

If you encounter any issues, this document will help you troubleshoot and resolve them.

## Webserver

### Can not connect
If you can not connect to the webserver, check the following:

- Make sure the webserver is running: `systemctl status rc-config-server`
- If it is not running, enable it and start:

```bash
sudo systemctl enable rc-config-server
sudo systemctl start rc-config-server
```

- If status is failed, check the logs: `journalctl -u rc-config-server -n 100`
