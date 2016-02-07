# Philips Hue Driver

## Requires

* Python 3
* [phue](https://github.com/studioimaginaire/phue)
* [XBOSDriver](https://github.com/gtfierro/XBOSDriver)

## Configuration

| key | meaning | example |
|-----|---------|---------|
|`bridge_ip` | IPv4 address of the Philips Hue bridge. | `192.168.1.242` |
|`report_rate` | Time in seconds between polls. Defaults to 10 seconds | 10 |
|`deviceID` | unique UUID for this deployment |  "f00ef112-cd75-11e5-ac2e-0001c009bf2f" |


## Notes

The first time the driver is started, be sure to press the physical button
on the Hue bridge less than 30 seconds before you start the driver. The library
will handle account creation.
