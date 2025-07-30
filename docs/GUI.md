# GUI
The GUI is designed to be straightforward to use. Press `[ESC]` at any time to toggle the menu.

Some settings require a **GUI restart** to take effect. Where this applies, a note is shown next to the setting.

## Debug output
For troubleshooting, you can run the GUI with debug logging enabled:

```bash
./v3xctrl-gui --log DEBUG
```

By default, only **ERROR** level messages and above are shown. The debug log includes:

* UI state changes
* Incoming/outgoing control messages
* Errors and exceptions

Logs are printed directly to the terminal where the GUI was started.

## Editing settings
On first start, a `settings.toml` file is generated with all available configuration values.

* **Not all settings are exposed in the GUI.**
You can manually edit settings.toml to access additional options.

* **Example use case:** Moving or resizing OSD (On-Screen Display) elements by adjusting their coordinates in the config file.

After manual edits, **restart the GUI** to apply changes.
