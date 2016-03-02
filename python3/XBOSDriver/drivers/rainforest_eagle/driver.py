from XBOSDriver import driver
import xml.etree.ElementTree as ET
import socket
import sys
import time

class RainforestEagleDriver(driver.Driver):
	def setup(self, opts):
		self.rate = int(opts.get('report_rate', 10))
		self.poll_rate = int(opts.get('poll_rate', 10))
		self.url = opts.get('url')
		self.multiplier = int(opts.get('multiplier', 1))

		xml = self.list_devices()
		root = ET.fromstring(xml)
		self.device = {}
		for child in root:
			self.device[child.tag] = child.text
		
		self.add_timeseries("/eagle/demand", "kW", "milliseconds", "numeric")
		self.add_timeseries("/eagle/summation_received", "kWh", "milliseconds", "numeric")
		self.add_timeseries("/eagle/summation_delivered", "kWh", "milliseconds", "numeric")
		for path, timeseries in self.timeseries.items():
			self.attach_metadata(path, {'Device': {
											'Manufacturer': self.device['Manufacturer'],
											'Model': self.device['ModelId']},
										'DeviceID': opts.get('deviceID'),
										'Name': opts.get('name')
										})

	def list_devices(self):
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.settimeout(5)
		s.connect((self.url, 5002))
		time.sleep(1)

		command = "<LocalCommand>\n <Name>list_devices</Name>\n</LocalCommand>\n"
		s.send(bytes(command, 'UTF-8'))
		return self.buffer_response(s)

	def get_device_data(self, mac_id):
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.settimeout(5)
		s.connect((self.url, 5002))
		time.sleep(1)

		command = '<LocalCommand>\n <Name>get_device_data</Name>\n <MacId>%s</MacId>\n</LocalCommand>\n' % mac_id
		s.send(bytes(command, 'UTF-8'))

		return self.buffer_response(s)

	@staticmethod
	def buffer_response(s):
		rv = bytearray()
		while 1:
			buf = s.recv(1024)
			if not buf:
				break
			rv += buf

		s.close()
		return rv.decode(encoding='UTF-8')

	def start(self):
		self.startPoll(self.poll, self.rate)

	def poll(self):
		try:
			xml = self.get_device_data(self.device['DeviceMacId'])
			# wrap in root element since response aint valid xml!
			xml = "<xml>\n" + xml + "\n</xml>"
			root = ET.fromstring(xml)
		
			# add demand reading
			ID = root.find('InstantaneousDemand')
		except Exception as e:
			print(e)
			return

		try:
			timestamp = int(ID.find('TimeStamp').text, 16)
			demand = int(ID.find('Demand').text, 16)
			dmultiplier = int(ID.find('Multiplier').text, 16)
			ddivisor = int(ID.find('Divisor').text, 16)
			fdemand = 1. * demand * dmultiplier / ddivisor
			fdemand *= self.multiplier
			self.add('/eagle/demand', fdemand)
			print('demand:', fdemand, 'kW')
		except ZeroDivisionError:
			pass
		except AttributeError:
			pass
	   
		# add summation readings
		CS = root.find('CurrentSummation')
		try:
			delivered = int(CS.find('SummationDelivered').text, 16)
			received = int(CS.find('SummationReceived').text, 16)
			smultiplier = int(CS.find('Multiplier').text, 16)
			sdivisor = int(CS.find('Divisor').text, 16)
			fdelivered = 1. * delivered * smultiplier / sdivisor
			freceived = 1. * received * smultiplier / sdivisor
			fdelivered *= self.multiplier
			freceived *= self.multiplier
			self.add('/eagle/summation_delivered', fdelivered)
			self.add('/eagle/summation_received', freceived)
			print('delivered:', fdelivered, 'kWh')
			print('received:', freceived, 'kWh')
		except AttributeError:
			pass
