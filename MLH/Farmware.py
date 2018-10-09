import os
import json
import requests
import datetime
import ast
import sys
import math
import time
import base64

#timezone
tz=0
# long date representation to date object
def l2d(long_s): return datetime.datetime.strptime(long_s, "%Y-%m-%dT%H:%M:%S.%fZ")
def s2d(short_s): return datetime.datetime.strptime(short_s, "%Y-%m-%d")
# date object to long date representation
def d2l(date): return date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
def d2s(date): return date.strftime("%Y-%m-%d")
def l2u(date): return date-datetime.timedelta(hours=tz)
def u2l(date): return date+datetime.timedelta(hours=tz)
def today_utc(): return datetime.datetime.utcnow()
def today_local(): return today_utc()+datetime.timedelta(hours=tz)

class Weather(object):
    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, fw):
        self.weather = {}
        self.fw=fw
    # ------------------------------------------------------------------------------------------------------------------
    def __repr__(self):
        return "Weather()"
    # ------------------------------------------------------------------------------------------------------------------
    def __str__(self):
        l=self.weather.items()
        l.sort(key=lambda x: s2d(x[0]),reverse=True)
        ret=""
        for r in l:
            ret+="{} : {: >05.2f}mm, [{: >6.2f} -{: >6.2f}]C\n".format(r[0],r[1]['rain24'],r[1]['min_temperature'],r[1]['max_temperature'])
        return ret
    # ------------------------------------------------------------------------------------------------------------------
    def __call__(self):
        return self.weather
    # ------------------------------------------------------------------------------------------------------------------
    def load(self):

        try:
            weather_station = None
            try:
                watering_tool = next(x for x in self.fw.tools() if 'water' in x['name'].lower())
                weather_station = next(x for x in self.fw.points() if x['pointer_type'] == 'ToolSlot'
                                       and x['tool_id'] == watering_tool['id'])
            except Exception as e:
                self.fw.log("No watering tool detected (I save weather into the watering tool meta)")

            self.weather = ast.literal_eval(weather_station['meta']['current_weather'])
            if not isinstance(self.weather, dict): raise ValueError
            # leave only last 7 days
            self.weather = {k: v for (k, v) in self.weather.items() if
                            datetime.date.today() - s2d(k).date() < datetime.timedelta(days=7)}

        except:  pass

    # ------------------------------------------------------------------------------------------------------------------
    def save(self):

        try:
            watering_tool = next(x for x in self.fw.tools() if 'water' in x['name'].lower())
            weather_station = next(x for x in self.fw.points() if x['pointer_type'] == 'ToolSlot'
                                   and x['tool_id'] == watering_tool['id'])
            weather_station['meta']['current_weather'] = str(self.weather)
        except:
            raise ValueError("No watering tool detected (I save weather into the watering tool meta)")
        self.fw.put('points/{}'.format(weather_station['id']), weather_station)



class Farmware(object):
    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self,app_name):
        self._points=None
        self._sequences=None
        self._tools=None
        self.args = {}
        self.debug=False
        self.local = False
        self.app_name=app_name
        self.weather=Weather(self)

        try:
            self.api_token = os.environ.get('API_TOKEN','')
            if self.api_token=='':  #this is local execution situation
                with open('../../Farmbot.lib/API_KEY.txt', 'r') as myfile:
                    self.api_token = myfile.read().replace('\n', '')

            self.farmware_url = os.environ.get('FARMWARE_URL','')
            if self.farmware_url == '':
                with open('../../Farmbot.lib/FARMWARE_URL.txt', 'r') as myfile:
                    self.farmware_url = myfile.read().replace('\n', '')

            self.headers = {'Authorization': 'Bearer ' + self.api_token, 'content-type': "application/json"}
            encoded_payload = self.api_token.split('.')[1]
            encoded_payload += '=' * (4 - len(encoded_payload) % 4)
            token = json.loads(base64.b64decode(encoded_payload).decode('utf-8'))
            self.bot_id=token['bot']
            self.api_url = 'https:'+token['iss']+'/api/'
            # self.api_url='https://my.farmbot.io/api/'
            self.mqtt_url = token['mqtt']
        except :
            print("API_TOKEN or FARMWARE_URL is not set, you gonna have a bad time")
            sys.exit(1)

    # ------------------------------------------------------------------------------------------------------------------
    def print_token(self, login, password):
        data = {'user': {'email': login, 'password': password}}
        response=self.post('tokens',data)

        print("Device id: {}".format(response['token']['unencoded']['bot']))
        print("MQTT Host: {}".format(response['token']['unencoded']['mqtt']))
        print("API_TOKEN: {}".format(response['token']['encoded']))
        return response
    # ------------------------------------------------------------------------------------------------------------------
    def load_config(self):
        global tz
        device = self.get('device')
        self.head = self.state()['location_data']['position']
        tz = device['tz_offset_hrs']


    # ------------------------------------------------------------------------------------------------------------------
    # loads config parameters
    def get_arg(self, name, default, tp):
        try:
            prefix = self.app_name.lower().replace('-', '_')
            if tp!=list:
                self.args[name] = tp(os.environ.get(prefix + '_'+name, default))
                if self.args[name] == 'None': self.args[name] = None
            else:
                self.args[name] = ast.literal_eval(os.environ.get(prefix + '_' + name, str(default)))
                if type(self.args[name])!=tp and self.args[name]!=None:
                    raise ValueError

            if name=='action':
                if self.args[name]!='real':
                    if self.args[name] == 'local': self.local = True
                    self.debug = True
                    self.log("TEST MODE, NO sequences or movement will be run, plants will NOT be updated",'warn')
        except:
            raise ValueError('Error parsing paramenter [{}]'.format(name))

        return self.args[name]


    # ------------------------------------------------------------------------------------------------------------------
    def log(self, message, message_type='info'):

        try:
            if not self.local:
                log_message = '[{}] {}'.format(self.app_name, message)
                node = {'kind': 'send_message', 'args': {'message': log_message, 'message_type': message_type}}
                response = requests.post(self.farmware_url + 'api/v1/celery_script', data=json.dumps(node),headers=self.headers)
                response.raise_for_status()
                message = log_message
        except: pass

        print(message)

    # ------------------------------------------------------------------------------------------------------------------
    def sync(self):
        if not self.debug:
            time.sleep(10)

        sync = ""
        for i in range(1,2):
            self.log("...actually syncing...")
            node = {'kind': 'sync', 'args': {}}
            response = requests.post(self.farmware_url + 'api/v1/celery_script', data=json.dumps(node),headers=self.headers)
            response.raise_for_status()

            cnt = 0
            for cnt in range(1,30):
                sync=self.state()['informational_settings']['sync_status']
                self.log("interim status {}".format(sync))
                if sync== "synced" or sync == "sync_error": break
                time.sleep(1)
            if cnt>=30: raise ValueError('Sync error, bot failed to complete syncing')
            if sync != "sync_error": break

        self.log('Sync status {}'.format(self.state()['informational_settings']['sync_status']))

    # ------------------------------------------------------------------------------------------------------------------
    def state(self):
            response = requests.get(self.farmware_url + '/api/v1/bot/state', headers=self.headers)
            response.raise_for_status()
            return response.json()

    # ------------------------------------------------------------------------------------------------------------------
    def get(self, enpoint):
        response = requests.get(self.api_url + enpoint, headers=self.headers)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------------------------------------------------------
    def delete(self, enpoint):
        if not self.debug:
            response = requests.delete(self.api_url + enpoint, headers=self.headers)
            response.raise_for_status()
            return
    # ------------------------------------------------------------------------------------------------------------------
    def post(self, enpoint, data):
        if not self.debug:
            response = requests.post(self.api_url + enpoint, headers=self.headers, data=json.dumps(data))
            response.raise_for_status()
            return response.json()

    # ------------------------------------------------------------------------------------------------------------------
    def put(self, enpoint, data):
        if not self.debug:
            response = requests.put(self.api_url + enpoint, headers=self.headers, data=json.dumps(data))
            response.raise_for_status()
            return response.json()

    # ------------------------------------------------------------------------------------------------------------------
    def patch(self, enpoint, data):
        if not self.debug:
            response = requests.patch(self.api_url + enpoint, headers=self.headers, data=json.dumps(data))
            response.raise_for_status()
            return response.json()

    # ------------------------------------------------------------------------------------------------------------------
    def execute_sequence(self, sequence, message=''):
        if sequence != None:
            if message != None:
                self.log('{}Executing sequence: {}({})'.format(message, sequence['name'].upper(), sequence['id']))
            if not self.debug:
                node = {'kind': 'execute', 'args': {'sequence_id': sequence['id']}}
                response = requests.post(self.farmware_url + 'api/v1/celery_script', data=json.dumps(node),
                                         headers=self.headers)
                response.raise_for_status()

    # ------------------------------------------------------------------------------------------------------------------
    def read_status(self):
        node = {'kind': 'read_status', 'args': {}}
        response = requests.post(self.farmware_url + 'api/v1/celery_script', data=json.dumps(node),
                                 headers=self.headers)
        response.raise_for_status()

    # ------------------------------------------------------------------------------------------------------------------
    def move_absolute(self, location, offset={'x': 0, 'y': 0, 'z': 0}, message=''):

        if message!=None:
            self.log('{}Moving absolute: {} {}'.format(message, str(location), "" if offset=={'y': 0, 'x': 0, 'z': 0} else str(offset)))

        node = {'kind': 'move_absolute', 'args':
            {
                'location': {'kind': 'coordinate', 'args': location},
                'offset': {'kind': 'coordinate', 'args': offset},
                'speed': 300
            }
                }

        if not self.debug:
            response = requests.post(self.farmware_url + 'api/v1/celery_script', data=json.dumps(node),
                                     headers=self.headers)
            response.raise_for_status()
        self.head = {'x': location['x']+offset['x'], 'y': location['y']+offset['y'], 'z': location['z']+offset['z']}

    # ------------------------------------------------------------------------------------------------------------------
    def points(self):
        if self._points!=None: return self._points
        self._points=self.get('points')
        return self._points

    # ------------------------------------------------------------------------------------------------------------------
    def plant_age(self, p):

        if p['pointer_type'].lower()!= 'plant': return 0
        if p['plant_stage'] != 'planted': return 0
        if p['planted_at'] == None: return 0
        return (today_utc() - l2d(p['planted_at'])).days + 1

    # ------------------------------------------------------------------------------------------------------------------
    def sequences(self):
        if self._sequences != None: return self._sequences
        self._sequences = self.get('sequences')
        return self._sequences

    # ------------------------------------------------------------------------------------------------------------------
    def tools(self):
        if self._tools != None: return self._tools
        self._tools = self.get('tools')
        return self._tools

    # ------------------------------------------------------------------------------------------------------------------
    def lookup_openfarm(self, plant):
        response = requests.get(
            'https://openfarm.cc/api/v1/crops?include=pictures&filter={}'.format(plant['openfarm_slug']), headers=self.headers)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------------------------------------------------------
    def distance(self, p1, p2):
        dx=math.fabs(p1['x']-p2['x'])
        dy = math.fabs(p1['y'] - p2['y'])
        return math.hypot(dx,dy)


