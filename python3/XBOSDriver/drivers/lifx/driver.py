from XBOSDriver import driver
import lifx

config = {
    #"report_destinations": ["http://bears.getxbos.org:8079/add/apikey"],
    "report_destinations": ["http://pantry.cs.berkeley.edu:8079/add/apikey"],
    "instanceUUID": "885891dc-cfbd-11e5-bef6-0cc47a0f7eea",
    "apikey": "dummyapikey",
    "archiver": "http://localhost:8079"
}

opts = {
    # deployment
    "bcast_addr": "10.4.10.255",
    "report_rate": 5,
    "deviceID": "8568faf2-cfbd-11e5-bef6-0cc47a0f7eea",
    "name": "Gabe Desk Light"
}

class LIFXDriver(driver.Driver):
    def setup(self, opts):
        self.rate = int(opts.get('report_rate', 10))

        lifx.network.BCAST = opts.get('bcast_addr', '255.255.255.255')
        lifx.network.debug = False
        lights = []

        while len(lights) == 0:
            lights = lifx.get_lights(['10.4.10.121'])
            print("Searching for lights...")

        self.lights = {l.bulb_label: l for l in lights}
        # assign numbers
        self.lightlabels = {idx: l for idx, l in enumerate(self.lights.values())}

        for idx, light in self.lightlabels.items():
            onpath = self.add_timeseries('/light{0}/on'.format(idx), 'On/Off', 'milliseconds', 'numeric')
            self.attach_metadata(onpath, {'Point': {'Type': 'Command', 'Command': 'On'}})

            huepath = self.add_timeseries('/light{0}/hue'.format(idx), 'Hue', 'milliseconds', 'numeric')
            self.attach_metadata(huepath, {'Point': {'Type': 'Command', 'Command': 'Hue'}})

            bripath = self.add_timeseries('/light{0}/brightness'.format(idx), 'Brightness', 'milliseconds', 'numeric')
            self.attach_metadata(bripath, {'Point': {'Type': 'Command', 'Command': 'Brightness'}})

        for path, timeseries in self.timeseries.items():
            self.attach_metadata(path, {'Location': {'Building': "Soda Hall",
                                                     'Room': '410 Gabe'},
                                        'SourceName': '410 Lights',
                                        'Device': {
                                            'Manufacturer': 'LIFX',
                                            'Model': 'LIFX'
                                            },
                                        'DeviceID': opts.get('deviceID'),
                                        'Name': opts.get('name'),
                                        'Lighting': {
                                            'Zone': 'Gabe Desk',
                                            'Type': 'Desklamp'
                                            }
                                        })

        self.attach_actuator(onpath, self.turnon, kind = driver.BINARY_ACTUATOR)
        self.attach_actuator(bripath, self.setbri, kind = driver.CONTINUOUS_ACTUATOR)

    def start(self):
        self.startPoll(self.poll, self.rate)

    def poll(self):
        for idx, light in self.lightlabels.items():
            light.get_state()
            self.add('/light{0}/on'.format(idx), int(light.power))
            self.add('/light{0}/hue'.format(idx), int(light.hue))
            self.add('/light{0}/brightness'.format(idx), int(light.brightness))

    def turnon(self, data):
        print("actuating on", data)
        for light in self.lights.values():
            if 'Readings' not in data: return
            print(data['Readings'][-1][1])
            light.set_power(data['Readings'][-1][1])

    def setbri(self, data):
        print("actuating bri", data)
        for light in self.lights.values():
            if 'Readings' not in data: return
            print(data['Readings'][-1][1])
            light.set_color(light.hue, light.saturation, data['Readings'][-1][1], light.kelvin, 500)

def run(dvr, config, opts):
    inst = dvr(config)
    inst.setup(opts)
    inst.prepare()
    inst.start()
    inst._dostart()

run(LIFXDriver, config, opts)
