# SMAP CLIENT

In the interest of simplifying code and rethinking some of the traffic patterns that have been emerging with the development of Giles and XBOS,
I think it is prudent to investigate new event loop frameworks that support the 'sMAP profile' and explore how sensing *and* actuation can
be done within a simple, lightweight framework that considers all used traffic patterns as first-class design decisions rather than afterthoughts
and provides an implementation that is both easy to understand and easy to integrate.

To "drive the point home", this repository will include client frameworks and examples in several languages. There is
a definite need for a simple framework to explore the sMAP protocol and how it jives with Giles the concepts of XBOS. This is that framework.

## Structure

Want to start simple; sMAP had the right idea. Each "framework" for a driver needs to implement these components:
* `setup`: read in the configuration file, declare timeseries and associated actuators and metadata
* `start`: after the `setup` has completed, the `start` setion will initialize the reporting loop and traffic pattern
* `poll` (also `read`): method is called each time to poll the underlying device or service. Following the `self.add` pattern of sMAP,
  values will be transformed and added to the timeseries
* `recv`: for push-based drivers, this method gets called every time the underlying device or service sends data to the running driver

Desired Features:
* *configuration at runtime*: timeseries, metadata, actuators, subscriptions should not need to be all configured in the `setup` section,
  but should be able to change w/n the driver
* *consistency with archiver* (also known as *single point of truth*): metadata in the drivers should reflect the metadata in the archiver,
  most likely as the result of a metadata subscription
* *handle push traffic*: a driver should be able to be the destination of an underlying services -- handling ports and push protocols in twisted
  was always very difficult, especially regarding ipv6

## Languages

### Python 2.x vs Python 3.x

Python 2.x event loops:
* [gevent](http://www.gevent.org/) -- requires an external C library, but seems to be the most popular choice
* [eventlet](http://eventlet.net/) -- based on libevent library, supposedly most people moving to gevent
* [twisted](https://twistedmatrix.com/trac/) -- pure Python, but limited support for IPv6 and rather heavyweight. Abstractions can be difficult to work with

Reasons to stick with Python2:
* many legacy libraries for old protocols still require Python 2 (e.g. OpenOPC, probably BACnet, etc)
* lots of people know Python 2 still

---

Python 3.x event loops:
* [asyncio](https://docs.python.org/3/library/asyncio.html) -- Python 3.4 onwards. Part of standard library, but API could still be changing on this. 
* [pulsar](http://quantmind.github.io/pulsar) -- actor-based, built over asyncio, provides a lot of nice facilities out of the box
