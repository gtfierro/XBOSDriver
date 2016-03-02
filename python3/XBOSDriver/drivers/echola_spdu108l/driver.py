from XBOSDriver import driver
import requests
from requests.auth import HTTPDigestAuth
from requests.exceptions import ConnectionError
import json
import xmltodict
import time

config = {
    "report_destinations": ["http://localhost:8079/add/apikey"],
    "instanceUUID": "4fcb759c-dc28-11e5-bb93-0cc47a0f7eea",
    "apikey": "dummyapikey",
    "archiver": "http://localhost:8079"
}

opts = {
    # deployment
    "ip": "10.4.10.132",
    "user": "admin",
    "password": "admin",
    "report_rate": 5,
    "name": "Gabe Desk Power Strip",
    "deviceID": "4d1d4302-dc28-11e5-bb93-0cc47a0f7eea"
}

class EcholaSPDU108LDriver(driver.Driver):
    def setup(self, opts):
        self.rate = int(opts.get('report_rate', 10))
        self.ip = opts.get('ip')
        self.user = opts.get('user', 'admin')
        self.password = opts.get('password', 'admin')
        self.readURL = 'http://' + self.ip + '/api.xml'
        self.actURL = 'http://' + self.ip + '/switch.cgi?out'

        for plug in range(1,9):
            onpath = self.add_timeseries("/echola/plug/{0}/on".format(plug), "On/Off", "milliseconds", "numeric")
            self.attach_metadata(onpath, {"Point": {"Type": "Reading", "Reading": "On/Off"}})

            powerpath = self.add_timeseries("/echola/plug/{0}/power".format(plug), "Watts", "milliseconds", "numeric")
            self.attach_metadata(powerpath, {"Point": {"Type": "Sensor", "Sensor": "Power"}})

        for path, timeseries in self.timeseries.items():
            self.attach_metadata(path, {'Device': {
                                            'Manufacturer': 'Echola',
                                            'Model': 'SPDU 108L'
                                            },
                                        'DeviceID': opts.get('deviceID'),
                                        'Name': opts.get('name'),
                                        })
        for plug in range(1,9):
            path = "/echola/plug/{0}/".format(plug)
            self.attach_actuator(path+"on", self.actuate_plug, kind=driver.BINARY_ACTUATOR, args=[plug])

    def start(self):
        self.startPoll(self.poll, self.rate)

    def poll(self):
        r = requests.get(self.readURL)
        data_dict = xmltodict.parse(r.content).get('response')
        for plug in range(1,9):
            self.add('/echola/plug/{0}/on'.format(plug), int(data_dict['pstate{0}'.format(plug)]))
            self.add('/echola/plug/{0}/power'.format(plug), float(data_dict['pow{0}'.format(plug)]))
    
    def actuate_plug(self, data, *args):
        plugnum = args[0]
        if 'Readings' not in data: return
        setting = data['Readings'][-1][1]
        print("Actuate plug {0} to {1}".format(plugnum, setting))

def run(dvr, config, opts):
    inst = dvr(config)
    inst.setup(opts)
    inst.prepare()
    inst.start()
    inst._dostart()

if __name__=='__main__':
    run(EcholaSPDU108LDriver, config, opts)
