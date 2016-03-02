import asyncio
import socket
import json
import uuid
import aiohttp
import logging
from tabulate import tabulate
logging.basicConfig(format='%(levelname)s:%(asctime)s %(name)s %(message)s', level=logging.INFO)
logger = logging.getLogger('driver')
logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

from XBOSDriver.timeseriestypes import UNIT_TIMES, STREAM_TYPES, UNIT_TIME_MAP
from XBOSDriver.timeseriestypes import STREAM_TYPE_NUMERIC
from XBOSDriver.exceptions import ValidationException, TimestampException, TimeseriesException
from XBOSDriver.subscribe import Subscriber
import XBOSDriver.util as util

BINARY_ACTUATOR = 'binary'
CONTINUOUS_ACTUATOR = 'continuous'

class Timeseries(object):
    def __init__(self, path, ts_uuid, unit_measure, unit_time, stream_type, is_actuator=False):
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
            'UnitofTime': UNIT_TIME_MAP[self.unit_time],
            'UnitofMeasure': self.unit_measure,
            'StreamType': self.stream_type
        }
        if self.stream_type == STREAM_TYPE_NUMERIC:
            self.properties['ReadingType'] = 'double' # sane default. No need for long
        # metadata for this timeseries
        self.metadata = {}
        # actuator timeseries
        self.actuator = None
        # whether or not there is metadata/properties that have yet to be committed
        self.dirty = True
        # if this stream is an actuator
        self.is_actuator = is_actuator

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
        self.buffer.append([time, value])

    def get_report(self):
        """
        Returns a JSON-serializable, sMAP-profile message containing all the metadata and readings
        to be sent to archiver
        """
        report = {"uuid": self.uuid, "Readings": self.buffer}
        if self.dirty:
            #TODO: just send the "diff"
            report["Properties"] = self.properties
            report["Metadata"] = self.metadata
            if self.actuator is not None:
                report["Actuator"] = {"uuid": self.actuator_uuid}
            elif self.is_actuator:
                report["Actuator"] = {"Model": self.model}
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
        self.dirty = True
        if self.actuator is not None:
            self.actuator.attach_metadata(metadata)

    def attach_actuator(self, kind=None, states=None, range=None):
        if self.is_actuator:
            raise ValidationException("Path {0} is already an actuator".format(self.path))
        if kind not in [BINARY_ACTUATOR, CONTINUOUS_ACTUATOR]:
            raise ValidationException("Actuator must be Binary or Continuous")
        self.actuator_uuid = str(uuid.uuid5(uuid.UUID(self.uuid), self.path+'_act'))
    #TODO: maybe define an attach_schedule to a timeseries? it would need to have an actuator on it
    #      and the method would automatically call that actuator and do the necessary conversions (or at least
    #      warn you when they were wrong). maybe "attach_actuation_source"? needs to be more general, e.g. for
    #      zone controllers too

class Driver(object):
    def __init__(self, config, base_metadata):
        # timeseries registered with this driver
        self.timeseries = {}
        # actuator paths registered
        self.actuators = {}
        self.instanceUUID = config.get('instance_uuid', uuid.uuid1())
        if not isinstance(self.instanceUUID, uuid.UUID):
            self.instanceUUID = uuid.UUID(self.instanceUUID)
        self.metadata = {}
        self._report_destinations = config.get('report_destinations', ",").split(',')
        # we introduce the archiver as a necessary part of driver configuration
        self._archiver = config.get('archiver', 'http://localhost:8079')
        self._udp4socks = {}
        self._tasks = []
        self.config = config

        # setup the base metadata for each timeseries to inherit as they are created
        self._base_metadata = util.build_recursive(base_metadata) if base_metadata is not None else {}

    def prepare(self):
        self._loop = asyncio.get_event_loop()

        if len(self._report_destinations) > 0:
            self._tasks.append(self._doreport())
            self._tasks.append(self._report())

    def add_subscription(self, query, callback, url=None, args=[]):
        if url is None:
            url = self._archiver+'/republish'
        subscription = Subscriber(url, query, callback, args)
        self._tasks.append(subscription.subscribe())

    def add_timeseries(self, path, unit_measure, unit_time, stream_type):
        # validate arguments
        if path in self.timeseries.keys():
            raise ValidationException("Path {0} is already registered as a timeseries ({1})".format(path, self.timeseries))
        else:
            ts_uuid = str(uuid.uuid5(self.instanceUUID, path))
            self.timeseries[path] = Timeseries(path, ts_uuid, unit_measure, unit_time, stream_type)
            # add default metadata. This can be replaced with attach_metadata
            self.attach_metadata(path, self._base_metadata)
        return path

    def attach_metadata(self, path, metadata):
        timeseries = self.timeseries.get(path, None)
        if timeseries is not None:
            timeseries.attach_metadata(metadata)
        else:
            self.metadata[path] = util.dict_merge(metadata, self.metadata[path])

    #TODO: right now this can only be done AFTER all the metadata changes. Make a timeseries reflect its metadata to its actuator automatically
    def attach_actuator(self, path, callback, kind=None, states=None, range=None, args=None):
        ts = self.timeseries.get(path, None)
        ts.attach_actuator(kind, states, range)
        if ts is None:
            raise ValidationException("Adding actuator to non-existant timeseries "+path)
            return

        # add in the actuator
        act_path = path+'_act'
        if act_path in self.actuators.keys():
            raise ValidationException("Path {0} is already registered as an actuator".format(act_path))
        else:
            ts.actuator = Timeseries(path+'_act', ts.actuator_uuid, ts.unit_measure, ts.unit_time, ts.stream_type, is_actuator=True)
            ts.actuator.attach_metadata(ts.metadata)
            ts.actuator.model = kind
            ts.actuator.states = states
            ts.actuator.range = range
            ts.actuator.callback = callback
            ts.actuator.args = args
            self.actuators[act_path] = ts.actuator
            self.add_subscription("Actuator/override = '{0}'".format(ts.actuator_uuid), callback, args=args)

    def attach_schedule(self, path, scheduleName, pointName):
        """
        We attach a schedule to an actuatable timeseries. We check if the timeseries has an associated actuator

        We start a subscription to the given schedulename and pointname: SUB where Schedule/Name = {scheduleName} and Schedule/Point/Name = {pointName}.
        We also add the following to our metadata:
            Schedule/Subscribed = {scheduleName}
            Schedule/Point/Subscribed = {pointName}

        We also start another subscription to ourselves so we know when our metadata has changed
        """
        ts = self.timeseries.get(path, None)
        # if this is not an actuator, then get the actuator
        if ts.is_actuator:
            raise ValidationException("Path {0} is an actuator. Please use the associated timeseries, not the actuator")
        elif ts.actuator == None: # ts does not have an actuator
                raise ValidationException("Path {0} cannot be scheduled because it is not an actuator or does not have an associated actuator".format(path))
        act = ts.actuator
        # here: 'act' is the actuator we want to schedule
        self.add_subscription("Metadata/Schedule/Name = '{0}' and Metadata/Schedule/Point/Name = '{1}'".format(scheduleName, pointName), act.callback, act.args)

        # add metadata for what schedule we subscribe to
        self.attach_metadata(path, {'Schedule': {'Subscribed': scheduleName,
                                                 'Point': {'Subscribed': pointName}}})

    def add(self, path, value, time=None):
        if path not in self.timeseries.keys():
            raise TimeseriesException("Path {0} not registered with this driver ({1})".format(path, self.timeseries))
        self.timeseries[path].add(value, time)

    def _send(self, url, data, headers):
        try:
            r = yield from aiohttp.request("POST", url, data=data, headers=headers)
            return r
        except Exception as e:
            print("error",url,e)

    def startPoll(self, func, rate):
        """
        Called by the subclassed driver to register the poll method
        Registers func to be called every rate seconds
        """
        self._tasks.append(self._startPoll(func, rate))

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
        self._tasks.append(self._listenUDP4(func, port, readsize))

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
                self._tasks
            )
        )

    @classmethod
    def run(klass, config, opts, metadata):
        inst = klass(config, metadata)
        inst.setup(opts)
        inst.prepare()
        inst.start()
        inst._dostart()

    #TODO: add report "added X points in the last minute w/ mean X, min Y max Z?"
    @asyncio.coroutine
    def _report(self):
        while True:
            yield from asyncio.sleep(self.rate)
            yield from self._doreport()

    @asyncio.coroutine
    def _doreport(self):
            try:
                # generate report
                report = {path: ts.get_report() for path, ts in self.timeseries.items()}
                report.update({path: act.get_report() for path, act in self.actuators.items()})
                if not len(report) > 0:
                    return # nothing to send

                table = []
                for path, ts in report.items():
                    if len(ts['Readings']) == 0: continue
                    values = [x[1] for x in ts['Readings']]
                    times = [x[0] for x in ts['Readings']]
                    table.append([path, len(ts['Readings']), min(values), max(values)])
                logger.info(tabulate(table))

                payload = json.dumps(report)
                headers = {'Content-type': 'application/json'}
                coros = [] # list of requests to send out
                logger.info("Sending reports to {0}...".format(self._report_destinations))
                for location in self._report_destinations:
                    coros.append(asyncio.Task(self._send(location, payload, headers)))
                responses = yield from asyncio.gather(*coros)
                for response in responses:
                    if response.status == 200:
                        logger.info("Report OK")
                        for ts in self.timeseries.values():
                            ts.clear_report()
                    else:
                        logger.warning("Report failed!", response.content)
                    response.close()
            except Exception as e:
                print("error", e)

    def recv(self, addr, data):
        pass
