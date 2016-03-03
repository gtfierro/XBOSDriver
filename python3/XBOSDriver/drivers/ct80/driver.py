from XBOSDriver import driver
import json
from requests.exceptions import ConnectionError
import requests

config = {
	"report_destinations": ["http://localhost:8079/add/apikey"],
	"instanceUUID": "7c72d5c6-df67-11e5-941b-5cc5d4ded1ae",
	"apikey": "dummyapikey",
	"archiver": "http://localhost:8079"
}

opts = {
	# deployment
	"ip": "10.4.10.111",
	"user": "admin",
	"password": "admin",
	"report_rate": 5,
	"name": "Gabe Desk Thermostat",
	"deviceID": "801788ac-df67-11e5-941b-5cc5d4ded1ae"
}

class CT80Driver(driver.Driver):
	def setup(self, opts):
		self.rate = int(opts.get('report_rate', 10))
		self.poll_rate = int(opts.get('poll_rate', 10))
		self.ip = opts.get('ip')
		self.url = 'http://' + self.ip + "/tstat"

		self._setpoints = {'t_heat': 60,
						   't_cool': 80}
		# list of API points
		self.points = [
						{"smapname": "temp", "name": "temp", "unit": "F"},
						{"smapname": "hvac_mode", "name": "tmode", "unit": "Mode"},
						{"smapname": "hvac_state", "name": "tstate", "unit": "State"},
						{"smapname": "fan_mode", "name": "fmode", "unit": "Mode"},
						{"smapname": "fan_state", "name": "fstate", "unit": "State"},
						{"smapname": "override", "name": "override", "unit": "Mode"},
						{"smapname": "hold", "name": "hold", "unit": "Mode"},
						{"smapname": "temp_heat", "name": "t_heat", "unit": "F"},
						{"smapname": "temp_cool", "name": "t_cool", "unit": "F"},
						{"smapname": "program_mode", "name": "program_mode", "unit": "Mode"}
					  ]
		for p in self.points:
			tspath = self.add_timeseries('/'+p['smapname'], p['unit'], 'milliseconds', 'numeric')
		self.add_timeseries('/humidity', '%RH', 'milliseconds','numeric')

		metadata_type = [
				('/temp','Sensor'),
				('/humidity','Sensor'),
				('/temp_heat','Setpoint'),
				('/temp_cool','Setpoint'),
				('/hold','Reading'),
				('/override','Reading'),
				('/hvac_mode','Reading'),
				('/fan_state','Reading'),
			]
		for path, tstype in metadata_type:
			self.attach_metadata(path,{'Point': {'Type':tstype}})
		self.attach_metadata('/temp', {'Point': {'Sensor': 'Temperature'}})
		self.attach_metadata('/humidity', {'Point': {'Sensor': 'Humidity'}})
		self.attach_metadata('/temp_heat', {'Point': {'Setpoint': 'Heating'}})
		self.attach_metadata('/temp_cool', {'Point': {'Setpoint': 'Cooling'}})

		for path, timeseries in self.timeseries.items():
			self.attach_metadata(path, {
										'Device': {
											'Manufacturer': 'Radio Thermostats America',
											'Model': 'CT80'
											},
										'DeviceID': opts.get('deviceID'),
										'Name': opts.get('name'),
										'HVAC': {
											'Type': 'Thermostat',
											}
										})
		self.attach_actuator('/temp_heat', self.recv_actuation, kind=driver.CONTINUOUS_ACTUATOR, args=('t_heat', ))
		self.attach_actuator('/temp_cool', self.recv_actuation, kind=driver.CONTINUOUS_ACTUATOR, args=('t_cool', ))

		self.attach_schedule('/temp_heat', 'weekday', 'Heating Setpoint')
		self.attach_schedule('/temp_cool', 'weekday', 'Cooling Setpoint')

	def start(self):
		self.startPoll(self.poll, self.poll_rate)

	def poll(self):
		try:
			r = requests.get(self.url)
		except ConnectionError as e:
			print('error connecting',e)
			return
		if not r.ok:
			print('got status code',r.status_code,'from api')
			return
		vals = json.loads(r.text)
		for p in self.points:
			if p['name'] not in vals or p['name'] in ['t_heat','t_cool']: # sometimes the ct80 hiccups and doesn't give data OR the mode limits what we see
				continue
			if type(vals[p['name']]) not in [int, float]:
				return
			if p['name'] == 'temp' and vals[p['name']] == -1:
				return
			self.add('/' + p["smapname"], float(vals[p["name"]]))

		# check which setpoint to write: if current temp is closer to heating setpoing,
		# set t_heat, else set t_cool
		if self._setpoints['t_heat'] is not None and self._setpoints['t_cool'] is not None:
			self.add('/temp_heat', float(self._setpoints['t_heat']))
			self.add('/temp_cool', float(self._setpoints['t_cool']))
			if abs(self._setpoints['t_heat'] - vals['temp']) < abs(self._setpoints['t_cool'] - vals['temp']):
				print('Writing temp_heat', self._setpoints['t_heat'])
				self.write_setting('t_heat', self._setpoints['t_heat'])
			else:
				print('Writing temp_cool', self._setpoints['t_cool'])
				self.write_setting('t_cool', self._setpoints['t_cool'])
		else: # publish the current t_heat, t_cool of the thermostat
			if 't_heat' in vals:
				self.add('/temp_heat', float(vals['t_heat']))
			if 't_cool' in vals:
				self.add('/temp_cool', float(vals['t_cool']))
		r = requests.get(self.url + '/humidity')
		val = json.loads(r.text)
		self.add('/humidity', float(val['humidity']))

	def write_setting(self, pointname, setting):
		print('actuating', pointname)
		payload = {pointname: setting}
		r = requests.post(self.url, data=json.dumps(payload))
		print(r)

	def recv_actuation(self, data, *args):
		pointname = args[0]
		if 'Readings' not in data: return
		setting = data['Readings'][-1][1]
		self.write_setting(pointname, setting)
		#if not request and self.name in ['t_heat','t_cool']:
		#	 self.driver._setpoints[self.name] = state
		#	 return
		#payload = '{"' + self.name + '": ' + str(state) + '}'
		#r = requests.post(self.url, data=payload)
		#return state
