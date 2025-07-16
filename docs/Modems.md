# Modems
This is a knowledge base for supported modems. Documentation is sparse at times and we tried to collect everything relevant in one place.

## Zero-4G-CAT1-Hub
This is the modem that is most widely available on Aliexpress, it is sold by different people under different names. The actual OEM seems to be **Mcuzone**. It comes in 4 distinct versions which is usually labeld on top of the MCU:

| Model    | Bands | GPS | Speed |
| -------- | ----- | --- | ----- |
| CAT1/LTE | 1, 3, 5, 8, 34, 38, 39, 40, 41 | No  | 10Mbps down, 5Mbps up. On Band 34 - 41: 6Mbps down, 4 Mbps up. |
| CAT1-GPS | 1, 3, 5, 8, 34, 38, 39, 40, 41 | No  | 10Mbps down, 5Mbps up. On Band 34 - 41: 6Mbps down, 4 Mbps up. |
| CAT1-EU  | 1, 3, 7, 8, 20, 28 | No  | 10Mbps down, 5Mbps up |
| CAT1-EA  | 1, 3, 5, 7, 8, 28 | No  | 10Mbps down, 5Mbps up |

To decide which one is the best for you, check  your area and provider on [cellmapper.net](https://www.cellmapper.net/map).


Here is a quick reference to enable all factory supported bands:

| Model    | all bands |
| -------- | --------- |
| CAT1-GPS | AT*BAND=5,0,0,482,149,1,1,0 |

### Debugging

> Before attempting any debugging make sure that yourn SIM card is actually working, put it in a phone, disable the PIN check - if enabled. And try to go online with it. Depending on your region you might also need to go through an activation process first.

Use `minicom` to connect to the modem:

```bash
minicom -D /dev/ttyACM0 -b 115200
```


#### Checking registration
Then invoke the following commands to check the modem status:

```bash
AT
AT+CPIN?
AT+COPS?
```

The output should look like this:

```
# Check that the modem is available
AT
AT

OK

# Check the SIM card status - if not READY, then likely PIN is not disabled
AT+CPIN?
AT+CPIN?

+CPIN: READY

OK

# Check operator - your output might differ, important is, that you see something here and that the first number is 0 and the last is 7 - the other ones are related to your exact operator
AT+COPS?
AT+COPS?

+COPS: 0,2,"23201",7

OK
```

At this point your modem is successfully registered to the mobile network with access technology LTE (that's what the 7 indicated in the last line).

#### Checking IP assignment
Just because your are registered does not mean you are ready to connect to the internet yet, you need to check for a valid PDP context:

```bash
AT+CGDCONT?
```

The output should look like this:

```bash
AT+CGDCONT?

+CGDCONT: 1,"IP","a1.net","10.54.1.125",0,0

OK
```

This denotes that you have a valid PDP context with a valid IPv4 address.

It is possible that you have multiple contexts available here:

```bash
AT+CGDCONT?

+CGDCONT: 1,"IP","a1.net","10.54.1.125",0,0
+CGDCONT: 2,"IPV6","a1.net","fe80::1234",0,0

OK
```

You can check the active contexts by invoking:

```bash
AT+CGACT?
```

```bash
+CGACT: 1,1
+CGACT: 2,1
```

This would indicate that both contexts are active.

If you want to make sure that only the IPv4 context is active, you can disable the IPv6 context:

```bash
AT+CGACT=0,2
```

> **NOTE:** Disabling a context might be reset upon restart of the modem.
