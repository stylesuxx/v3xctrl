# Modems

This is a knowledge base for supported modems. Documentation is sparse at times, so we have collected relevant information here in one place.

## Zero-4G-CAT1-Hub

This is the modem most widely available on AliExpress, sold under different  names by different vendors. The actual OEM appears to be **Mcuzone**.
It comes in **four distinct versions**, usually labeled on top of the MCU:

| Model    | Bands | GPS | Speed |
|----------|-------|-----|-------|
| CAT1/LTE | 1, 3, 5, 8, 34, 38, 39, 40, 41 | No  | 10Mbps down, 5Mbps up. On Band 34 - 41: 6Mbps down, 4 Mbps up. |
| CAT1-GPS | 1, 3, 5, 8, 34, 38, 39, 40, 41 | No  | 10Mbps down, 5Mbps up. On Band 34 - 41: 6Mbps down, 4 Mbps up. |
| CAT1-EU  | 1, 3, 7, 8, 20, 28 | No  | 10Mbps down, 5Mbps up |
| CAT1-EA  | 1, 3, 5, 7, 8, 28 | No  | 10Mbps down, 5Mbps up |

> **TIP:** Check which LTE bands are used by your carrier in your area on [cellmapper.net](https://www.cellmapper.net/map) before purchasing a modem..


### Enabling All Factory-Supported Bands

Example for CAT1-GPS:

| Model    | AT command |
|----------|------------|
| CAT1-GPS | AT*BAND=5,0,0,482,149,1,1,0 |

### Debugging

> Before attempting any debugging, make sure your SIM card is active and working. Insert it into a phone first, **disable the PIN code** if necessary, and verify that you can connect to the internet.
In some regions, you may need to complete an activation process before the SIM can register on the network.

Connect to the modem using `minicom`:

```bash
minicom -D /dev/ttyACM0 -b 115200
```

#### Checking Network Registration

Run these commands to check modem status:

```bash
AT
AT+CPIN?
AT+COPS?
```

Example output:

```
# Check modem availability
AT
AT

OK

# Check SIM status
AT+CPIN?
AT+CPIN?

+CPIN: READY

OK

# Check operator registration
AT+COPS?
AT+COPS?

+COPS: 0,2,"23201",7

OK
```

* `23201` is the MCC/MNC (operator code).
* The last value `7` indicates LTE connection (other values may indicate GSM/UMTS).

At this point, the modem is successfully registered on the mobile network with LTE access.

#### Checking IP assignment
Registration does not guarantee an active data session. Check your PDP context:

```bash
AT+CGDCONT?
```

Expected output:

```bash
AT+CGDCONT?

+CGDCONT: 1,"IP","a1.net","10.54.1.125",0,0

OK
```

This indicates you have a valid IPv4 address.

If multiple contexts are active:

```bash
AT+CGDCONT?

+CGDCONT: 1,"IP","a1.net","10.54.1.125",0,0
+CGDCONT: 2,"IPV6","a1.net","fe80::1234",0,0

OK
```

List active contexts:

```bash
AT+CGACT?
```

```bash
+CGACT: 1,1
+CGACT: 2,1
```

Disable IPv6 if needed:

```bash
AT+CGACT=0,2
```

> **NOTE:** Context changes may reset after a modem reboot.

## AT command cheat sheet
Useful commands when evaluating or debugging new modems.

> For more advanced scripting, try [python ATlib](https://pypi.org/project/atlib).

### Get Firmware version:

```
AT+VER?
```

### Check Network Registration

```
AT+CREG?

# Not connected
+CREG: 0,0

# Connected
+CREG: 0,1
```

### Show Currently Used Band

```
AT*BANDIND?
*BANDIND: 0, 3, 7
```

Here, the middle number (`3`) is the LTE band currently in use.
