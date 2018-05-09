import os
import json
import requests

class Farmware:
    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self,app_name):
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
        response = requests.delete(self.api_url + enpoint, headers=self.headers)
        response.raise_for_status()
        return response.json()
    # ------------------------------------------------------------------------------------------------------------------
    def post(self, enpoint, data):
        response = requests.put(self.api_url + enpoint, headers=self.headers, data=json.dumps(data))
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------------------------------------------------------
    def put(self, enpoint, data):
        response = requests.put(self.api_url + enpoint, headers=self.headers, data=json.dumps(data))
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------------------------------------------------------
    def patch(self, enpoint, data):
        response = requests.patch(self.api_url + enpoint, headers=self.headers, data=json.dumps(data))
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------------------------------------------------------
    def execute_sequence(self, sequence, debug=False, message=''):
        if sequence != None:
            if message != None:
                self.log('{}Executing sequence: {}({})'.format(message, sequence['name'].upper(), sequence['id']))
            if not debug:
                node = {'kind': 'execute', 'args': {'sequence_id': sequence['id']}}
                response = requests.post(os.environ['FARMWARE_URL'] + 'api/v1/celery_script', data=json.dumps(node),
                                         headers=self.headers)
                response.raise_for_status()

    # ------------------------------------------------------------------------------------------------------------------
    def move_absolute(self, location, offset, debug=False, message=''):

        if message!=None:
            self.log('{}Moving absolute: {} {}'.format(message, str(location), "" if offset=={'y': 0, 'x': 0, 'z': 0} else str(offset)))

        node = {'kind': 'move_absolute', 'args':
            {
                'location': {'kind': 'coordinate', 'args': location},
                'offset': {'kind': 'coordinate', 'args': offset},
                'speed': 300
            }
                }

        if not debug:
            response = requests.post(os.environ['FARMWARE_URL'] + 'api/v1/celery_script', data=json.dumps(node),
                                     headers=self.headers)
            response.raise_for_status()


