# SIM
To get your modem going with a new SIM card and make things as easy as possible, follow these steps:

## 1. Activate the SIM Card
This might not be necessary in your country, but at least in the EU you will have to activate your SIM card with your provider. You can usually do this on the website of your chosen provider or in person when you buy the SIM card. You will need some kind of ID.

## 2. Test in Phone & disable PIN
Insert your SIM card in a phone, make sure it registers with the network and that you can connect to the internet. Preferably - if your phone allows it - lock it to 4G/LTE.

In the security settings, disable the PIN. Reboot your phone, make sure it does not ask for the PIN anymore and that you still register with the network and connect to the internet.

## 3. Test in Modem
Insert your SIM card in the modem and start the streamer.

> **NOTE:** You will need to start the streamer with the SIM card inserted or you will have to manually reboot the modem after inserting the SIM card: AT+CFUN=1,1

### Web Interface
TODO

### CLI
From the CLI connect to the modem:

```bash
minicom -D /dev/ttyACM0 -b 115200
```

#### Check that the modem is available
```bash
AT

# Result
AT
```

#### Check that SIM is recognized and PIN is disabled
```bash
AT+CPIN?

# SUCCESS
+CPIN: READY

# FAIL - SIM not recognized
+CME ERROR: 10
```

#### Check tat the SIM is registered with the carrier

```bash
AT+COPS?

# SUCCESS
+COPS: 0,2,"23201",7
```

On success you should always see a 7 at the end, indicating that the access technology is LTE.

`23201` is the carrier code. First three numbers are country code, last two carrier code - in our case `232` is Austria and `01` is A1.

#### Check context and IP assignment

```bash
AT+CGDCONT?

# SUCCESS IPv4 AND v6 (1)
+CGDCONT: 1,"IPV4V6","ctnet","IPV4:10.0.28.161    IPV62001:4BB8:02CC:18F7:0000:0000:E33A:AA8E",,,,0,,,,,,1,,

# SUCCESS IPv4 (2)
+CGDCONT: 1,"IP","magenta","10.145.10.20",,,,,,,,,,,,

# FAIL
```

In case (1) we have an IPV4V6 context. Also we are using the ctnet APN - for chinese telekom. But we are not registered to this carrier - still we get an IP address and internet is working. This means that most likely the provider ignores the wrong APN and rewrites to the default APN on the backend.

When checking the public IP address, it turns out, that it in-fact belongs to A1.


##### Setting APN
We want to prefer IPv4 and in cases where no APN is assigned, we can do so ourselves. A valid APN might not be necessary and the provider might ignore it, but it is a good idea to use the official one.

**Automatically**
This will set context 1 to an IPv4 context without an APN assigned, it should then be automatically assigned by the carrier after modem reboots:

```bash
AT+CGDCONT=1,"IP",""
AT+CFUN=1,1
```

Check:

```bash
AT+CGDCONT?

# SUCCESS
+CGDCONT: 1,"IP","webapn.at","10.73.79.219",0,0
```

**Manually**
Explicitly set the APN of your carrier:

```bash
AT+CGDCONT=1,"IP","webapn.at"
AT+CFUN=1,1
```

Check:

```bash
AT+CGDCONT?

# SUCCESS
+CGDCONT: 1,"IP","webapn.at","10.73.79.219",0,0
```
## Switching SIMs
Switching between SIM cards is easily possible if you ran through the setup steps above. Just insert the new SIM card and powercycle the streamer (or reset the modem via AT commands).

```bash
AT+CFUN=1,1
```

## Quirks
We have found that some SIM cards will not automatically register when roaming is enabled. This means that you should always disable roaming when setting or locking bands:

```bash
AT*BAND=5,0,0,482,149,1,1,0
```

Roaming is the third to last parameter, you can verify it the following way:

```bash
AT*BAND=5,0,0,482,149
AT+CFUN=1,1
```

If your SIM does no longer automatically connect, pass the parameter to disable roaming and see the SIM automagically register:

```bash
AT*BAND=5,0,0,482,149,1
AT+CFUN=1,1
```

Alternatively you can try forcing registration with a certain carrier:

```bash
#AT+COPS=1,2,"<MNC+MCC>"
AT+COPS=1,2,"23201"
```

## Miscelanious and maybe helpful

Full reset and auto connect setup
```bash
AT+CFUN=0
AT+COPS=0
AT*BAND=5,0,0,482,149,1
AT+CGDCONT=1,"IP",""
AT+CFUN=1,1
```

Checking things:
```
AT+CPIN?
AT+CGATT?
AT+COPS?
AT+CGDCONT?
AT+CGPADDR
AT*BANDIND?

# Scan
AT+COPS=?
```

### AT*BAND command explained
```
AT*BAND=<mode>,<GSMband>,<UMTSband>,<LTEbandH>,<LTEbandL>,<roamingConfig>,<srvDom>,<bandPriorityFlag>
```

* `mode` 5 only - LTE network
* `GSMband` 0 only - not relevant
* `UMTSband` 0 only - not relevant
* `LTEbandH` depends on region
* `LTEbandL` depends on region
* `roamingConfig` 0,1,2 (yes, no, no-change)
* `srvDom` can only be 1
* `bandPriorityFlag` 0,1,2 (default, TDD, FDD)
