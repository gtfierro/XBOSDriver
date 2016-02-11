from XBOSDriver import driver
import phue

config = {
    "report_destinations": ["http://localhost:8079/add/apikey"],
    "instanceUUID": "3229aa0e-cd50-11e5-b7ad-0001c009bf2f",
    "apikey": "dummyapikey",
    "archiver": "http://localhost:8079"
}

opts = {
    # deployment
    "bridge_ip": "192.168.1.242",
    "report_rate": 5,
    "name": "Gabe Desk Light",
    "deviceID": "f00ef112-cd75-11e5-ac2e-0001c009bf2f"
}

class PhilipsHueDriver(driver.Driver):
    def setup(self, opts):
        self.rate = int(opts.get('report_rate', 10))

        self.bridge = phue.Bridge(opts.get('bridge_ip'))
        self.bridge.connect()

        self.registered_lights = set()

        # load the lights
        for light_id, light_status in self.bridge.get_api()['lights'].items():
            if light_status['state']['reachable']:
                # add timeseries for on/off, hue, brightness
                onpath = self.add_timeseries('/light{0}/on'.format(light_id), 'On/Off', 'milliseconds', 'numeric')
                self.attach_metadata(onpath, {'Point': {'Type': 'State', 'State': 'On/Off'}})

                huepath = self.add_timeseries('/light{0}/hue'.format(light_id), 'Hue', 'milliseconds', 'numeric')
                self.attach_metadata(huepath, {'Point': {'Type': 'State', 'State': 'Hue'}})

                bripath = self.add_timeseries('/light{0}/brightness'.format(light_id), 'Brightness', 'milliseconds', 'numeric')
                self.attach_metadata(bripath, {'Point': {'Type': 'State', 'State': 'Brightness'}})

                self.registered_lights.add(light_id)

        # TODO: have a library of metadata configurations for common things, e.g. light brightness, etc

        for path, timeseries in self.timeseries.items():
            self.attach_metadata(path, {'Location': {'Building': "Gabe's Apartment",
                                                     'Room': 'Bedroom'},
                                        'SourceName': 'Gabe House',
                                        'Device': {
                                            'Manufacturer': 'Philips',
                                            'Model': 'Philips Hue'
                                            },
                                        'DeviceID': opts.get('deviceID'),
                                        'Name': opts.get('name'),
                                        'Lighting': {
                                            'Zone': 'Bedroom',
                                            'Type': 'Desklamp'
                                            }
                                        })


    def start(self):
        self.startPoll(self.poll, self.rate)

    def poll(self):
        for light_id, light_status in self.bridge.get_api()['lights'].items():
            if light_status['state']['reachable']:
                if light_id not in self.registered_lights:
                    self.add_timeseries('/light{0}/on'.format(light_id), 'On/Off', 'seconds', 'numeric')
                    self.add_timeseries('/light{0}/hue'.format(light_id), 'Hue', 'seconds', 'numeric')
                    self.add_timeseries('/light{0}/brightness'.format(light_id), 'Brightness', 'seconds', 'numeric')
                    self.registered_lights.add(light_id)
                self.add('/light{0}/on'.format(light_id), int(light_status['state']['on']))
                self.add('/light{0}/hue'.format(light_id), int(light_status['state']['hue']))
                self.add('/light{0}/brightness'.format(light_id), int(light_status['state']['bri']))


def run(dvr, config, opts):
    inst = dvr(config)
    inst.setup(opts)
    inst.prepare()
    inst.start()
    inst._dostart()

run(PhilipsHueDriver, config, opts)
