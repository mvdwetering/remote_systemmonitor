# REMOTE SYSTEMMONITOR

> This is still work in progress

This is basically a the [Home Assistant SystemMonitor integration](https://www.home-assistant.io/integrations/systemmonitor/), but with the data collector part split off so it can get data from a remote system.

Just monitoring, nothing else.

## Known limitations

Missing sensors compared to normal System Monitor

* Processes, I don't have a usecase right now
* Temperature, Windows and my WSL dev env have no temperatures so can't test
* Swap, I don't have or even know the use case for it

## Collector

The collector can be run by installing the requirements and running the script like with the commands below.
You might need to allow your firewall to let it listen to the port (2604 by default)

```
python3 -m pip install -r requirements_collector.txt
python3 rsm_collector.py
```

## Background

I had been looking into options for monitoring my Windows fileserver (CPU load, memory and disk usage), but all options I tried had issues.

I looked at/tried Glances, hddtemp, OpenHardware Monitor, SystemBridge and IoTLink.

Some of those issues are:

* Not running on Windows
* Sending data (including API key) in plaintext over the network (which is not really an issue for monitoring, but unacceptable for control).
* No way to disable controlling of system services (I don't need my server to be controllable and certainly not when data is not encrypted)
* No way to disable exposing of multimedia files in Home Assistant (I have other means of sharing my media, it just clutters/confuses the HA media library views)
* Stability issues
* I want a direct integration with Home Assistant, not through an additional MQTT server

After initially trying to build something new and fancy I decided that was going to take too much time to do properly, so hacking SystemMonitor seems the easy way out.

## Technical debt

Because of the quick-and-dirty way is it implemented there is are a lot of loose ends and hacks that would need to be resolved to get to a more maintainable state. These are just the highlights, there is more...

The API is just the `json.dumps(original data)` which does not work well for the named tuple data types (they become strings). Hacks have been added to decode those strings back into datatypes as workaround.
Proper solution would be to define an API and make it serializable. This might be amost the API classes as defined in the `rsm_collector_api.py`.

API documentation would be nice instead of having to read the source. Or even a real spec (OpenApi or OpenRPC) with validators and all.

Repo could be split up in separate ones for API definition, HA integration and the collector.

Probably quite some commented and unused code left.

No unittests :(

API does not have proper exceptions on setup and connection failure detection, but somehow it kind of seems to work?

The "dummy" subscriptions don't seem to work properly. There is a `set('y', 'm', 'd', 'u')` instead, but it works...

Actually the subscriptions are just hacked to be always enabled. This could be improved by either getting rid of them completely or have a way that clients can subscribe for the stuff they are interested in and the collector would then only collect data that is asked for. Not sure if that would be worth the effort and the amount of resources it would save.

Make myjsonrpc a proper package instead of the hacky symlink to share it between HA integration and collector.

Myjsonrpc was built because other JSONRPC packages did not seem to support receiving notificastions from servers. Maybe recheck and if really not available try to get support in some of the existing packages. No real need to add yet another JSON RPC.

If the above is not feasible improve myjsonrpc. 

* The intention was to have "pure" separated `send` and `receive` calls, but receive got a return value for convenience. Probably could have solved by providing a context to allow the transport to piece things together.
* Make better tests
* Test against other implementations
* Try to implement an HTTP based transport
* Define an AbstractTransport to make clear what is expected of a Transport implementation