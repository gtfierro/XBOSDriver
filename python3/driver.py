import asyncio
import socket
import json
import uuid
import aiohttp

from timeseriestypes import UNIT_TIMES, STREAM_TYPES
from timeseriestypes import STREAM_TYPE_NUMERIC
from exceptions import ValidationException, TimestampException, TimeseriesException
import subscribe
import util

class Timeseries(object):
    def __init__(self, path, ts_uuid, unit_measure, unit_time, stream_type):
        # validate
        Timeseries._validate_unit_measure(unit_measure)
        Timeseries._validate_unit_time(unit_time)
        Timeseries._validate_stream_type(stream_type)

        # add to instance variables
        # the path of this timeseries
        self.path = path
        # buffer of uncommitted readings
        self.buffer = []
        # the unique identifier for this timeseries
        self.uuid = ts_uuid
        # properties for this timeseries
        self.unit_measure = unit_measure
        self.unit_time = unit_time
        self.stream_type = stream_type
        self.properties = {
            'UnitofTime': self.unit_time,
            'UnitofMeasure': self.unit_measure,
            'StreamType': self.stream_type
        }
        if self.stream_type == STREAM_TYPE_NUMERIC:
            self.properties['ReadingType'] = 'double' # sane default. No need for long
        # metadata for this timeseries
        self.metadata = {}
        # whether or not there is metadata/properties that have yet to be committed
        self.dirty = True

    def __repr__(self):
        return "<Timeseries Path={path} UnitofMeasure={uom} UnitofTime={uot} StreamType={st}".format(
                    path=self.path,
                    uom=self.unit_measure,
                    uot=self.unit_time,
                    st=self.stream_type
                )

    @staticmethod
    def _validate_unit_measure(unit_measure):
        if unit_measure is None:
            raise ValidationException("unit_measure is NONE")
        if not isinstance(unit_measure, str):
            raise ValidationException("unit_measure must be string")

    @staticmethod
    def _validate_unit_time(unit_time):
        if unit_time is None:
            raise ValidationException("unit_time is NONE")
        if unit_time not in UNIT_TIMES:
            raise ValidationException("unit_time must be one of {0}".format(UNIT_TIMES))

    @staticmethod
    def _validate_stream_type(stream_type):
        if stream_type not in STREAM_TYPES:
            raise ValidationException("stream_type must be one of {0}".format(STREAM_TYPES))

    def _validate_value(self, value):
        if self.stream_type == STREAM_TYPE_NUMERIC:
            if not isinstance(value, (int, float)):
                raise ValidationException("Value {0} is not of type STREAM_TYPE_NUMERIC".format(value))

    def add(self, value, time=None):
        """
        Queues the given value to be sent to the archiver
        """
        #TODO: handle unit of time
        #TODO: timezone support
        self._validate_value(value)
        if time is None:
            time = util.get_current_time_as(self.unit_time)
        self.buffer.append([value, time])

    def get_report(self):
        """
        Returns a JSON-serializable, sMAP-profile message containing all the metadata and readings
        to be sent to archiver
        """
        report = {self.path: {"uuid": self.uuid, "Readings": self.buffer}}
        if self.dirty:
            #TODO: just send the "diff"
            report["Properties"] = self.properties
            report["Metadata"] = self.metadata
        return report

    def clear_report(self):
        """
        Clears the local buffer of uncommitted readings
        """
        #TODO: only clear since last write
        self.buffer = []
        self.dirty = False

    def attach_metadata(self, metadata):
        """
        Attaches metadata to this timeseries following update/insert policy
        """
        self.metadata = util.dict_merge(metadata, self.metadata)
        print('md is now', self.metadata)
        self.dirty = True

class Driver(object):
    def __init__(self, opts):
        # timeseries registered with this driver
        self.timeseries = {}
        self.instanceUUID = opts.get('instanceUUID', uuid.uuid1())
        if not isinstance(self.instanceUUID, uuid.UUID):
            self.instanceUUID = uuid.UUID(self.instanceUUID)
        self.metadata = {}
        self._report_destinations = opts.get('report_destinations', [])
        self._udp4socks = {}

        # handle options
        print(opts)
        self.rate = int(opts.get('rate', 1))
        self.counter = 0
        for i in range(opts.get('num_timeseries')):
            self.add_timeseries('/sensor{0}'.format(i), "V", "seconds", "numeric")

        print(self.timeseries)

        for path, timeseries in self.timeseries.items():
            self.attach_metadata(path, {'Location': {
                                          'Building': 'Soda Hall',
                                          'Campus': 'UC Berkeley'
                                         },
                                        'Sourcename': 'Demo Source'
                                       })

        for path, timeseries in self.timeseries.items():
            self.attach_metadata(path, {'Location': {
                                          'Room': '410',
                                         }
                                       })


        print("Starting...")
        self._loop = asyncio.get_event_loop()

        self.subscription = subscribe.Subscriber('http://localhost:8079/republish2', 'select * where has uuid', self.subscribecb)

        self.tasks = [asyncio.Task(self.subscription.subscribe())]

        if len(self._report_destinations) > 0:
            self.tasks.append(self._report())


    def subscribecb(self, msg):
        print("callback!", msg)


    def add_timeseries(self, path, unit_measure, unit_time, stream_type):
        # validate arguments
        if path in self.timeseries.keys():
            raise ValidationException("Path {0} is already registered as a timeseries ({1})".format(path, self.timeseries))
        else:
            ts_uuid = str(uuid.uuid5(self.instanceUUID, path))
            self.timeseries[path] = Timeseries(path, ts_uuid, unit_measure, unit_time, stream_type)

    def attach_metadata(self, path, metadata):
        timeseries = self.timeseries.get(path, None)
        if timeseries is not None:
            timeseries.attach_metadata(metadata)
        else:
            self.metadata[path] = util.dict_merge(metadata, self.metadata[path])

    def add(self, path, value, time=None):
        if path not in self.timeseries.keys():
            raise TimeseriesException("Path {0} not registered with this driver ({1})".format(path, self.timeseries))
        self.timeseries[path].add(value, time)

    def _send(self, url, data, headers):
        try:
            print("send", data, headers)
            r = yield from aiohttp.request("POST", url, data=data, headers=headers)
            return r
        except Exception as e:
            print("error",e)

    def startPoll(self, func, rate):
        """
        Called by the subclassed driver to register the poll method
        Registers func to be called every rate seconds
        """
        self.tasks.append(self._startPoll(func, rate))

    @asyncio.coroutine
    def _startPoll(self, func, rate):
        """
        Calls func every rate seconds
        """
        while True:
            yield from asyncio.sleep(rate)
            func()

    def listenUDP4(self, func, port, readsize=1024):
        if not isinstance(port, int):
            raise ValidationException("Port {0} must be int".format(port))
        if port in self._udp4sock:
            raise SmapSocketException("Port {0} is already used for UDP4: {1}".format(port, self._udp4sock))
        self._udp4sock[port] = socket.socket(AF_INET, SOCK_DGRAM)
        self._udp4sock[port].bind(("0.0.0.0", int(port)))
        self.tasks.append(self._listenUDP4(func, port, readsize))

    @asyncio.coroutine
    def _listenUDP4(self, func, port, readsize):
        while True:
            data = yield from self._udp4sock[port].read(readsize)
            func(data.decode())

    def _dostart(self):
        """
        Starts the event loop with the registered tasks
        """
        self._loop.run_until_complete(
            asyncio.wait(
                self.tasks
            )
        )

    @asyncio.coroutine
    def _report(self):
        while True:
            yield from asyncio.sleep(self.rate)
            try:
                # generate report
                report = {path: ts.get_report() for path, ts in self.timeseries.items()}
                if not len(report) > 0:
                    continue # nothing to send

                payload = json.dumps(report)
                headers = {'Content-type': 'application/json'}
                coros = [] # list of requests to send out
                for location in self._report_destinations:
                    coros.append(asyncio.Task(self._send(location, payload, headers)))
                r = yield from asyncio.gather(*coros)
                for ts, resp in zip(self.timeseries.values(), r):
                    if resp.status == 200:
                        ts.clear_report()
            except Exception as e:
                print("error", e)


    def poll(self):
        self.counter += 1
        print("polling, counter is {0}".format(self.counter))
        for path, timeseries in self.timeseries.items():
            self.add(path, self.counter)

    def recv(self, addr, data):
        pass

config = {
    "report_destinations": ["http://localhost:8079/add/apikey"],
    "num_timeseries": 1,
    "rate": 1,
    "instanceUUID": "f92f89ac-40ec-11e5-b998-5cc5d4ded1ae"
}

d = Driver(config)
d.startPoll(d.poll, 1)
d._dostart()
