import driver

config = {
    "report_destinations": ["http://localhost:8079/add/apikey"],
    "instanceUUID": "f92f89ac-40ec-11e5-b998-5cc5d4ded1ae",
    "apikey": "dummyapikey",
    "archiver": "http://localhost:8079"
}


opts = {
    "num_timeseries": 1,
    "rate": 1,
}

def run(dvr, config, opts):
    inst = dvr(config)
    inst.setup(opts)
    inst.prepare()
    inst.start()
    inst._dostart()


class SampleDriver(driver.Driver):
    def setup(self, opts):
        print("opts", opts)
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

        self.add_subscription("select distinct Metadata/Schedule/Name where has Metadata/Schedule/Name", self.schedlist, url=self.config['archiver']+'/republish2')
        self.add_subscription("Metadata/Schedule/Point/Name = 'Heating Setpoint' and Metadata/Schedule/Name = 'weekday'", self.schedulecb)

    def schedulecb(self, res):
        print("got CB", res)

    def schedlist(self, l):
        print("new list of schedules", l)

    def start(self):
        # calls self.poll at @rate seconds
        self.startPoll(self.poll, self.rate)

        #driver.listenUDP4(self.recvUDP, 8000, readsize=1024)
        #driver.listenTCP4(self.recvTCP, 8000)
        #driver.listenUDP6(self.recvUDP, 8000)
        #driver.listenTCP6(self.recvTCP, 8000)
        #driver.listenWebSocket(self.recvWS, 8000) #TODO: need path?

    def poll(self):
        self.counter += 1
        print("polling, counter is {0}".format(self.counter))
        for path, timeseries in self.timeseries.items():
            self.add(path, self.counter)

run(SampleDriver, config, opts)
