from XBOSDriver import driver
import requests
from requests.auth import HTTPDigestAuth
from requests.exceptions import ConnectionError
import json
import time

config = {
    "report_destinations": ["http://localhost:8079/add/apikey"],
    "instanceUUID": "996893b8-d068-11e5-bef6-0cc47a0f7eea",
    "apikey": "dummyapikey",
    "archiver": "http://localhost:8079"
}

opts = {
    # deployment
    "ip": "10.4.10.111",
    "user": "admin",
    "password": "admin",
    "report_rate": 20,
    "poll_rate": 10,
    "name": "Gabe Desk Thermostat",
    "deviceID": "96f75948-d068-11e5-bef6-0cc47a0f7eea"
}

class IMT550CDriver(driver.Driver):
    def setup(self, opts):
        self.rate = int(opts.get('report_rate', 10))
        self.poll_rate = int(opts.get('poll_rate', 10))
        self.ip = opts.get('ip')
        self.user = opts.get('user', None)
        self.password = opts.get('password', None)
        self.points0 = [
                          {"name": "temp", "unit": "F", "data_type": "double",
                            "OID": "4.1.13", "range": (-30.0,200.0),
                            "access": 4, "devtosmap": lambda x: x/10,
                            "smaptodev": lambda x: x*10,
                            "act_type": None}, # thermAverageTemp
                          {"name": "humidity", "unit": "%RH",
                           "data_type": "double", "OID": "4.1.14",
                            "range": (0,95), "access": 0,
                            "devtosmap": lambda x: x, "smaptodev": lambda x: x,
                            "act_type": "continuous"}, #thermRelativeHumidity
                          {"name": "hvac_state", "unit": "Mode",
                            "data_type": "long",
                            "OID": "4.1.2", "range": [0,1,2], "access": 4,
                            "devtosmap":  lambda x: {1:0, 2:0, 3:1, 4:1, 5:1, 6:2, 7:2, 8:0, 9:0}[x],
                            "smaptodev":  lambda x: {x:x}[x],
                            "act_type": "discrete"}, # thermHvacState
                          {"name": "fan_state", "unit": "Mode", "data_type": "long",
                            "OID": "4.1.4", "range": [0,1], "access": 4,
                            "devtosmap":  lambda x: {0:0, 1:0, 2:1}[x],
                            "smaptodev": lambda x: x,
                            "act_type": "binary"}, # thermFanState
                          {"name": "temp_heat", "unit": "F", "data_type": "double",
                            "OID": "4.1.5", "range": (45.0,95.0), "access": 6,
                            "devtosmap": lambda x: x/10, "smaptodev": lambda x: x*10,
                            "act_type": "continuous"}, #thermSetbackHeat
                          {"name": "temp_cool", "unit": "F", "data_type": "double",
                            "OID": "4.1.6",
                            "range": (45.0,95.0), "access": 6,
                            "devtosmap": lambda x: x/10, "smaptodev": lambda x: x*10,
                            "act_type": "continuous"}, #thermSetbackCool
                          {"name": "hold", "unit": "Mode",
                            "data_type": "long", "OID": "4.1.9",
                            "range": [0,1], "access": 6,
                            "devtosmap": lambda x: {1:0, 2:1, 3:0}[x],
                            "smaptodev": lambda x: {0:1, 1:2}[x],
                            "act_type": "binary"}, # hold/override
                          {"name": "override", "unit": "Mode",
                            "data_type": "long", "OID": "4.1.9",
                            "range": [0,1], "access": 6,
                            "devtosmap": lambda x: {1:0, 3:1, 2:0}[x],
                            "smaptodev": lambda x: {0:1, 1:3}[x],
                            "act_type": "binary"}, # hold/override
                          {"name": "hvac_mode", "unit": "Mode", "data_type": "long",
                            "OID": "4.1.1", "range": [0,1,2,3],
                            "access": 6,
                            "devtosmap": lambda x: x-1,
                            "smaptodev": lambda x: x+1,
                            "act_type": "discrete"}, # thermHvacMode
                          {"name": "fan_mode", "unit": "Mode", "data_type": "long",
                            "OID": "4.1.3", "range": [1,2,3], "access": 6,
                            "devtosmap": lambda x: x, "smaptodev": lambda x: x,
                            "act_type": "discrete"} # thermFanMode
                       ]
        ts = {}
        for p in self.points0:
            ts[p['name']] = self.add_timeseries('/' + p["name"], p["unit"], 'milliseconds', 'numeric')

        # setup metadata for each timeseries
        metadata_type = [
                ('/temp','Sensor'),
                ('/humidity','Sensor'),
                ('/temp_heat','Setpoint'),
                #('/temp_heat_act','Setpoint'),
                ('/temp_cool','Setpoint'),
                #('/temp_cool_act','Setpoint'),
                ('/hold','Reading'),
                #('/hold_act','Command'),
                ('/override','Reading'),
                #('/override_act','Command'),
                ('/hvac_mode','Reading'),
                #('/hvac_mode_act','Command')
            ]

        #print(ts)
        for path, tstype in metadata_type:
            self.attach_metadata(path,{'Point': {'Type':tstype}})

        self.attach_metadata('/temp', {'Point': {'Sensor': 'Temperature'}})
        self.attach_metadata('/humidity', {'Point': {'Sensor': 'Humidity'}})
        self.attach_metadata('/temp_heat', {'Point': {'Setpoint': 'Heating'}})
        self.attach_metadata('/temp_cool', {'Point': {'Setpoint': 'Cooling'}})


        for path, timeseries in self.timeseries.items():
            self.attach_metadata(path, {
                                        'Device': {
                                            'Manufacturer': 'Proliphix',
                                            'Model': 'IMT550C'
                                            },
                                        'DeviceID': opts.get('deviceID'),
                                        'Name': opts.get('name'),
                                        'HVAC': {
                                            'Zone': 'Gabe Desk',
                                            'Type': 'Thermostat',
                                            }
                                        })
        self.attach_actuator('/temp_cool', self.set_cooling_setpoint, kind=driver.CONTINUOUS_ACTUATOR, args=('cool', ))
        self.attach_actuator('/temp_heat', self.set_heating_setpoint, kind=driver.CONTINUOUS_ACTUATOR, args=('heat', ))

        self.attach_schedule('/temp_heat', 'weekday', 'Heating Setpoint')
        self.attach_schedule('/temp_cool', 'weekday', 'Cooling Setpoint')

    def set_heating_setpoint(self, data, *args):
        print("GOT DATA", data, args)
        if 'Readings' not in data: return
        setting = data['Readings'][-1][1]
        print("got data HEAT", data, setting)
        payload = {"OID4.1.5": int(setting*10), "submit": "Submit"}
        r = requests.get('http://'+self.ip+"/pdp/",
            auth=HTTPDigestAuth(self.user, self.password), params=payload)
        print(r)

    def set_cooling_setpoint(self, data, *args):
        print("GOT DATA", data, args)
        if 'Readings' not in data: return
        setting = data['Readings'][-1][1]
        print("got data COOL", data, setting)
        payload = {"OID4.1.6": int(setting*10), "submit": "Submit"}
        r = requests.get('http://'+self.ip+"/pdp/",
            auth=HTTPDigestAuth(self.user, self.password), params=payload)
        print(r)

    def start(self):
        self.startPoll(self.poll, self.poll_rate)

    def poll(self):
        for p in self.points0:
            url = 'http://%s/get?OID%s' % (self.ip, p["OID"])
            try:
                r = requests.get(url, auth=HTTPDigestAuth(self.user, self.password))
                if not r.ok:
                    print('got status code',r.status_code,'from api')
                    time.sleep(5)
                    return
                val = r.text.split('=', 1)[-1]
                # when the thermostat reboots, sometimes we get extraneous readings
                if abs(int(val)) > 20000:
                    time.sleep(5)
                    return
                print(p["name"],val)
                self.add("/" + p["name"], p['devtosmap'](float(val)))
            except Exception as e:
                print('error connecting',e)
                time.sleep(5)
                return

def run(dvr, config, opts):
    inst = dvr(config)
    inst.setup(opts)
    inst.prepare()
    inst.start()
    inst._dostart()

if __name__=='__main__':
    run(IMT550CDriver, config, opts)
