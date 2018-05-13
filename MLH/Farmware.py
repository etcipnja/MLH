import os
import json
import requests
import datetime
import time

#timezone
tz=0
# long date representation to date object
def l2d(long_s): return datetime.datetime.strptime(long_s, "%Y-%m-%dT%H:%M:%S.%fZ")
def s2d(short_s): return datetime.datetime.strptime(short_s, "%Y-%m-%d")
# date object to long date representation
def d2l(date): return date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
def d2s(date): return date.strftime("%Y-%m-%d")
# retrun today in UTC
def today_utc(): return datetime.datetime.utcnow()


class Farmware:
    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self,app_name):
        self.debug=False
        self.app_name=app_name
        self.api_url = 'https://my.farmbot.io/api/'
        try:
            self.headers = {'Authorization': 'Bearer ' + os.environ['API_TOKEN'], 'content-type': "application/json"}
        except :
            print("API_TOKEN is not set, you gonna have bad time")

    # ------------------------------------------------------------------------------------------------------------------
    def log(self, message, message_type='info'):

        try:
            log_message = '[{}] {}'.format(self.app_name, message)
            node = {'kind': 'send_message', 'args': {'message': log_message, 'message_type': message_type}}
            response = requests.post(os.environ['FARMWARE_URL'] + 'api/v1/celery_script', data=json.dumps(node),headers=self.headers)
            response.raise_for_status()
            message = log_message
        except: pass

        print(message)

    # ------------------------------------------------------------------------------------------------------------------
    def sync(self):
        if not self.debug:
            node = {'kind': 'sync', 'args': {}}
            response = requests.post(os.environ['FARMWARE_URL'] + 'api/v1/celery_script', data=json.dumps(node),headers=self.headers)
            response.raise_for_status()

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
            response = requests.put(self.api_url + enpoint, headers=self.headers, data=json.dumps(data))
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
                response = requests.post(os.environ['FARMWARE_URL'] + 'api/v1/celery_script', data=json.dumps(node),
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
            response = requests.post(os.environ['FARMWARE_URL'] + 'api/v1/celery_script', data=json.dumps(node),
                                     headers=self.headers)
            response.raise_for_status()


