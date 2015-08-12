import asyncio
import time
import json
from timeseriestypes import UNIT_TIMES, STREAM_TYPES
from timeseriestypes import STREAM_TYPE_NUMERIC
from exceptions import ValidationException, TimestampException, TimeseriesException
import util
from aiohttp import web

class Timeseries(object):
    def __init__(self, path, unit_measure, unit_time, stream_type):
        # validate
        Timeseries._validate_unit_measure(unit_measure)
        Timeseries._validate_unit_time(unit_time)
        Timeseries._validate_stream_type(stream_type)

        # add to instance variables
        self.path = path
        self.unit_measure = unit_measure
        self.unit_time = unit_time
        self.stream_type = stream_type

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
        #TODO: handle unit of time
        #TODO: timezone support
        self._validate_value(value)
        if time is None:
            time = util.get_current_time_as(self.unit_time)
        return {self.path: {"Readings": (value, time)}}


class Driver(object):
    def __init__(self, opts):
        # timeseries registered with this driver
        self.timeseries = {}
        self._tosend = []
        self._report_destinations = opts.get('report_destinations', [])

        # handle options
        print(opts)
        self.rate = int(opts.get('rate', 1))
        self.counter = 0
        for i in range(opts.get('num_timeseries')):
            self.add_timeseries('/sensor{0}'.format(i), "V", "seconds", "numeric")

        print(self.timeseries)

        print("Starting...")
        self._loop = asyncio.get_event_loop()
        tasks = [self.start()]
        if len(self._report_destinations) > 0:
            tasks.append(self._report())

        self._loop.run_until_complete(
            asyncio.wait(
                tasks
            )
        )


    def add_timeseries(self, path, unit_measure, unit_time, stream_type):
        # validate arguments
        if path in self.timeseries.keys():
            raise ValidationException("Path {0} is already registered as a timeseries ({1})".format(path, self.timeseries))
        else:
            self.timeseries[path] = Timeseries(path, unit_measure, unit_time, stream_type)

    def add(self, path, value, time=None):
        if path not in self.timeseries.keys():
            raise TimeseriesException("Path {0} not registered with this driver ({1})".format(path, self.timeseries))
        reading = self.timeseries[path].add(value, time)
        self._tosend.append(reading)

    def _send(self):
        if not len(self._tosend) > 0:
            return # nothing to send
        payload = {path: message for timeseries in self._tosend for path, message in timeseries.items()}
        print(payload)

    @asyncio.coroutine
    def start(self):
        while True:
            yield from asyncio.sleep(self.rate)
            self.poll()

    @asyncio.coroutine
    def _report(self):
        while True:
            yield from asyncio.sleep(self.rate)
            self._send()


    def poll(self):
        self.counter += 1
        print("polling, counter is {0}".format(self.counter))
        for path, timeseries in self.timeseries.items():
            self.add(path, self.counter)

config = {
    "report_destinations": ["http://localhost:8079/add/apikey"],
    "num_timeseries": 2,
    "rate": 1
}

d = Driver(config)
