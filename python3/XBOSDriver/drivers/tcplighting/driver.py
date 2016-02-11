from XBOSDriver import driver
from lxml import etree
import requests

config = {
    "report_destinations": ["http://localhost:8079/add/apikey"],
    "instanceUUID": "0021a0ca-cf5d-11e5-bef6-0cc47a0f7eea",
    "apikey": "dummyapikey",
    "archiver": "http://localhost:8079"
}

opts = {
    # deployment
    "bridge_ip": "10.4.10.103",
    "report_rate": 5,
    "deviceID": "ea3baa30-cf5c-11e5-bef6-0cc47a0f7eea"
}

class TCPLightingDriver(driver.Driver):
    def setup(self, opts):
        self.rate = int(opts.get('report_rate', 10))
        self.bridge = TCPBridge(opts.get('bridge_ip'))

    def start(self):
        self.startPoll(self.poll, self.rate)

    def poll(self):
        return


class TCPBridge:
    headers = {"Content-Type": "text/xml"}
    # 0: the command, e.g. GWRLogin, 1: the XML,
    commands = {
        'GWRLogin': '<gip><version>1</version><email>admin</email><password>admin</password></gip>',
        'GatewayGetInfo': '<gip><version>1</version><token>{token}</token><fwnew>1</fwnew></gip>',
        'DeviceSendCommand': '<gip><version>1</version><token>{token}</token><did>{device_id}</did><value>{state}</value></gip>',
        'DeviceSendCommandLevel': '<gip><version>1</version><token>{token}</token><did>{device_id}</did><value>{state}</value><type>level</type></gip>',
        'Info': '<gwrcmds><gwrcmd><gcmd>SceneGetList</gcmd><gdata><gip><version>1</version><token>{token}</token><fields>activeonly,bigicon,detail,imageurl</fields><islocal>1</islocal></gip></gdata></gwrcmd></gwrcmds>',
        'State': '<gwrcmds><gwrcmd><gcmd>RoomGetCarousel</gcmd><gdata><gip><version>1</version><token>{token}</token><fields>name,image,imageurl,control,power,product,class,realtype,status</fields></gip></gdata></gwrcmd></gwrcmds>'
    }

    def __init__(self, ip):
        self.ip = ip
        self.posturl = 'https://'+ip+'/gwr/gop.php'
        print(self.posturl)
        self.token = '1234567890' #self.get_token()
        self.gateway_id, self.framework_version, self.serial_number = self.get_serverinfo()
        self.devices = self.get_states()

        print("DEVICES", devices)

    def command(self, cmd, data):
        #c = 'cmd={0}&data={1}&fmt=xml'.format(x, y).replace('%26','&').replace('%3D','=').replace('/','%2F')
        c = {'cmd': cmd, 'data': data, 'fmt': 'xml'}
        #c = 'cmd={0}&data={1}&fmt=xml'.format(cmd, data)
        return c

    def get_token(self):
        command = self.commands['GWRLogin']
        data = self.command('GWRLogin',command)
        resp = requests.post(self.posturl, headers=self.headers, params=data, verify=False)
        xml = resp.content
        parsed = etree.fromstring(xml)
        print(xml)
        token = parsed.xpath('//gip')[0].find('token').text
        return token

    def get_serverinfo(self):
        command = self.commands['GatewayGetInfo'].format(token=self.token)
        data = self.command('GatewayGetInfo', command)
        resp = requests.post(self.posturl, headers=self.headers, params=data, verify=False)
        xml = resp.content
        print(xml)
        parsed = etree.fromstring(xml)
        gateway_id = parsed.find('gateway').find('gid').text
        framework_version = parsed.find('gateway').find('fwversion').text
        serial_number = parsed.find('gateway').find('serial').text
        return gateway_id, framework_version, serial_number

    def set_state(self, device_id,state):
        xmldata = self.commands['DeviceSendCommand'].format(token=self.token,device_id=device_id,state=state)
        resp = requests.post(self.posturl, headers=self.headers, data=self.command('DeviceSendCommand',xmldata))
        xml = resp.content
        parsed = etree.fromstring(xml)

    def set_level(self, device_id,state):
        xmldata = self.commands['DeviceSendCommandLevel'].format(token=self.token,device_id=device_id,state=state)
        resp = requests.post(self.posturl, headers=self.headers, data=self.command('DeviceSendCommand',xmldata))
        xml = resp.content
        parsed = etree.fromstring(xml)

    def get_states(self):
        resp = requests.post(self.posturl, headers=self.headers, data=self.command('GWRBatch', self.commands['State'].format(token=self.token)))
        xml = resp.content
        parsed = etree.fromstring(xml)
        devices = parsed.xpath('//device')
        device_ids = [x.find('did').text for x in devices]
        states = [x.find('state').text for x in devices]
        power = [x.find('power').text for x in devices]
        levels = map(lambda x: x.text, filter(lambda x: x is not None, [x.find('level') for x in devices]))
        return zip(device_ids, states, power, levels)

    def get_deviceinfo(self, token):
        resp = requests.post(self.posturl, headers=self.headers, data=self.command('GWRBatch',self.commands['Info'].format(token=self.token)))
        xml = resp.content
        parsed = etree.fromstring(xml)
        devices = parsed.xpath('//device')
        device_ids = [x.find('id').text for x in devices]
        readings = [x.findall('cmd') for x in devices]
        values = [int(x[0].getchildren()[1].text) for x in readings]
        levels = [int(x[1].getchildren()[1].text) for x in readings]
        return zip(device_ids, values, levels)


def run(dvr, config, opts):
    inst = dvr(config)
    inst.setup(opts)
    inst.prepare()
    inst.start()
    inst._dostart()

if __name__ == '__main__':
    run(TCPLightingDriver, config, opts)
