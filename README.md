# REMOTE SYSTEMMONITOR

> This is still work in progress

This is basically a the [Home Assistant SystemMonitor integration](https://www.home-assistant.io/integrations/systemmonitor/), but split off the data collectin part so it can get data from a remote system.

Just monitoring, nothing else.

## Background

I had been looking into options for monitoring my Windows fileserver (CPU load, memory and disk usage), but all options I tried had issues.

I looked at/tried Glances, hddtemp, OpenHardware Monitor, SystemBridge and IoTLink.

Some of those issues are:

* Not running on Windows
* Sending data (including API key) in plaintext over the network.
* No way to disable controlling of systemC services (I don't need my server to be controllable and certainly not when data is not encrypted)
* No way to disable exposing of multimedia files in Home Assistant (I have other means of sharing my media)
* Stability issues
* I want a direct integration with Home Assistant, not through an additional MQTT server

After initially trying to build something new and fancy I decided that was going to take too much time to do properly, so hacking SystemMonitor seems the easy way out.
