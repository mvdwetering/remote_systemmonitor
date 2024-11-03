# Remote System Monitor

This is basically a the [Home Assistant SystemMonitor integration](https://www.home-assistant.io/integrations/systemmonitor/), but with the data collector part split off so it can get data from a remote system.

Just monitoring, nothing else.

> Note that this is/was a quick-ish side project and I don't intend to extend it with new features. 
> Only keep it working if changes are required in upcoming Home Assistant releases.

## Known limitations

Missing sensors compared to normal System Monitor

* Processes, I don't have a use-case right now
* Temperature, Windows and my WSL dev env have no temperatures (would like the temps though)
* Swap, I don't have a use-case for it

## Collector

### Installation

Download the source from the releases page and extract it somewhere where you want to keep it.

Create a virtual environment, activate it and install the requirements.

```
python3 -m venv venv
```

Activate the virtual environment, depends on OS and terminal

```
# Windows CMD
venv\Scripts\activate.bat
# Linux
. ./venv/bin/activate
```

With the virtual environment active install the requirements.

```
(venv)> python3 -m pip install -r requirements_collector.txt
```

### Running

Make sure the virtual environment is active, see above.

Then run with the command below.
You might need to allow your firewall to let it listen to the port (2604 by default)

```
python3 rsm_collector.py
```

## Home Assistant installation

### Home Assistant Community Store (HACS)

*Recommended because you get notified of updates.*

HACS is a 3rd party downloader for Home Assistant to easily install and update custom integrations made by the community. More information and installation instructions can be found on their site https://hacs.xyz/

* Open the HACS page
* Add this repository as a custom repo through the ⋮ menu as type "Integration"
* Search for "Remote SystemMonitor" and click it
* Press the Download button and wait for it to download
* Restart Home Assistant

Then install the integration as usual:
* Go to the "Integration" page in Home Assistant (Settings > Devices & Services)
* Press the "Add Integration" button
* Search for "Remote SystemMonitor" and select the integration.
* Follow the instructions

### Manual

* Go to the releases section and download the zip file.
* Extract the zip
* Copy the contents to the `custom_components` directory in your `config` directory.
* Restart Home Assistant

Then install the integration as usual:
* Go to the "Integration" page in Home Assistant (Settings > Devices & Services)
* Press the "Add Integration" button
* Search for "Remote SystemMonitor" and select the integration.
* Follow the instructions


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

## Future

Ideas for future someone

* Make the connection encrypted. Probably easiest to use secure websockets (wss://)
* Add access management? E.g. an API key (or per client)
* Restructure the data. Currently it is based on how it comes out of `psutil`. Maybe organize as a component with measurements and a machine is a collection of components. That way there would be one compnent per storage device (HDD/SSD) and it would contain all measurements/capabilities for that, so usage, but also temperature if available. Components could also expose more data like manufacturere, firmware version etc...
* Figure out and document how to run it as a Windows Service, so it runs all the time without someone needing to be logged in and start it
* Add more data like temperatures. Maybe some high level SMART data. Manufacturer and OS version could be nice to expose on the device in Home Assistant.
* Only send data that changed
* Implement re-configure
* Maybe expose "components" as devices? There was an accepted archtecture proposal for sub-devices which would fit really nicely
* Expose Mac addresses as a connection to Home Assistant so it can link with other integrations using Mac ocnnections like routers and Wake-on-LAN
