import asyncio
import json
import uuid
import aiohttp

from timeseriestypes import UNIT_TIMES, STREAM_TYPES
from timeseriestypes import STREAM_TYPE_NUMERIC
from exceptions import ValidationException, TimestampException, TimeseriesException
import util

class Timeseries(object):
    def __init__(self, path, ts_uuid, unit_measure, unit_time, stream_type):
        # validate
        Timeseries._validate_unit_measure(unit_measure)
        Timeseries._validate_unit_time(unit_time)
        Timeseries._validate_stream_type(stream_type)

        # add to instance variables
        self.path = path
        self.uuid = ts_uuid
        self.unit_measure = unit_measure
        self.unit_time = unit_time
        self.stream_type = stream_type
        self.metadata = {}
        self.properties = {
            'UnitofTime': self.unit_time,
            'UnitofMeasure': self.unit_measure,
            'StreamType': self.stream_type
        }
        if self.stream_type == STREAM_TYPE_NUMERIC:
            self.properties['ReadingType'] = 'double' # sane default. No need for long

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
        #TODO: handle unit of time
        #TODO: timezone support
        self._validate_value(value)
        if time is None:
            time = util.get_current_time_as(self.unit_time)
        return {self.path: {"uuid": self.uuid, "Readings": [[value, time]]}}

    def attach_metadata(self, metadata):
        self.metadata = util.dict_merge(metadata, self.metadata)
        print('md is now', self.metadata)

class Driver(object):
    def __init__(self, opts):
        # timeseries registered with this driver
        self.timeseries = {}
        self.instanceUUID = opts.get('instanceUUID', uuid.uuid1())
        if not isinstance(self.instanceUUID, uuid.UUID):
            self.instanceUUID = uuid.UUID(self.instanceUUID)
        self.metadata = {}
        self._tosend = []
        self._report_destinations = opts.get('report_destinations', [])

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
        reading = self.timeseries[path].add(value, time)
        self._tosend.append(reading)

    def _send(self, url, data, headers):
        try:
            print("send", data, headers)
            r = yield from aiohttp.request("POST", url, data=data, headers=headers)
            yield from r.text()
            print("resp",r)
        except Exception as e:
            print("error",e)

    @asyncio.coroutine
    def start(self):
        while True:
            yield from asyncio.sleep(self.rate)
            self.poll()

    @asyncio.coroutine
    def _report(self):
        while True:
            yield from asyncio.sleep(self.rate)
            try:
                if not len(self._tosend) > 0:
                    continue # nothing to send
                payload = {path: message for timeseries in self._tosend for path, message in timeseries.items()}
                data = json.dumps(payload)
                data = data.replace("'",'"')
                headers = {'Content-type': 'application/json'}

                coros = [] # list of requests to send out
                for location in self._report_destinations:
                    coros.append(asyncio.Task(self._send(location, data, headers)))
                yield from asyncio.gather(*coros)
            except Exception as e:
                print("error", e)


    def poll(self):
        self.counter += 1
        print("polling, counter is {0}".format(self.counter))
        for path, timeseries in self.timeseries.items():
            self.add(path, self.counter)

config = {
    "report_destinations": ["http://localhost:8079/add/apikey"],
    "num_timeseries": 1,
    "rate": 1,
    "instanceUUID": "f92f89ac-40ec-11e5-b998-5cc5d4ded1ae"
}

d = Driver(config)
