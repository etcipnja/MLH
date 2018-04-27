import os
import json
import requests
import ast
import datetime

APP_NAME = ((__file__.split(os.sep))[len(__file__.split(os.sep)) - 3]).replace('-master', '')


class Farmware():
    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self):
        self.api_url = 'https://my.farmbot.io/api/'
        try:
            api_token = os.environ['API_TOKEN']
        except KeyError:
            raise ValueError('API_TOKEN not set')

        self.headers = {'Authorization': 'Bearer ' + api_token, 'content-type': "application/json"}

    # ------------------------------------------------------------------------------------------------------------------
    def handle_error(self, response):
        if response.status_code != 200:
            raise ValueError(
                "{} {} returned {}".format(response.request.method, response.request.path_url, response.status_code))
        return

    # ------------------------------------------------------------------------------------------------------------------
    def log(self, message, message_type='info'):

        # try:
        #    log_message = '[{}] {}'.format(APP_NAME, message)
        #    node = {'kind': 'send_message', 'args': {'message': log_message, 'message_type': message_type}}
        #    ret = requests.post(os.environ['FARMWARE_URL']+'api/v1/celery_script', data=json.dumps(node), headers=self.headers)
        #    message = log_message
        # except: pass

        print(message)

    # ------------------------------------------------------------------------------------------------------------------
    def get(self, enpoint):
        response = requests.get(self.api_url + enpoint, headers=self.headers)
        self.handle_error(response)
        return response.json()

    # ------------------------------------------------------------------------------------------------------------------
    def put(self, enpoint, data):
        response = requests.put(self.api_url + enpoint, headers=self.headers, data=json.dumps(data))
        self.handle_error(response)
        return response.json()

    # ------------------------------------------------------------------------------------------------------------------
    def execute_sequence(self, sequence, debug=False):
        if sequence['id'] != -1:
            self.log(
                '{}Executing sequence: {}({})'.format("" if not debug else "DEBUG ", sequence['name'], sequence['id']))
            if not debug:
                node = {'kind': 'execute', 'args': {'sequence_id': sequence['id']}}
                response = requests.post(os.environ['FARMWARE_URL'] + 'api/v1/celery_script', data=json.dumps(node),
                                         headers=self.headers)
                self.handle_error(response)

    # ------------------------------------------------------------------------------------------------------------------
    def move_absolute(self, location, offset, debug=False):
        self.log('{}Moving absolute: {} {}'.format("" if not debug else "DEBUG ", str(location), str(offset)))

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
            self.handle_error(response)


class MLH(Farmware):
    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self):
        Farmware.__init__(self)

        prefix = APP_NAME.lower().replace('-', '_')
        self.params = {}

        filter = os.environ.get(prefix + "_filter_meta", "[('plant_stage','planned')]")
        save = os.environ.get(prefix + "_save_meta", "[('plant_stage','planned'),('del','*')]")

        try:
            self.params['filter_meta'] = ast.literal_eval(filter)
            self.params['save_meta'] = ast.literal_eval(save)  # \"date\",\"today\"
        except:
            raise ValueError("Invalid meta {} or {}".format(filter, save))

        self.params['pointname'] = os.environ.get(prefix + "_pointname", 'Carrot')
        self.params['sequence'] = {'init': {'name': os.environ.get(prefix + '_init', 'None'), 'id': -1},
                                   'before': {'name': os.environ.get(prefix + '_before', 'None'), 'id': -1},
                                   'after': {'name': os.environ.get(prefix + '_after', 'None'), 'id': -1},
                                   'end': {'name': os.environ.get(prefix + '_end', 'None'), 'id': -1}}

        self.params['default_z'] = int(os.environ.get(prefix + "_default_z", -300))
        self.params['action'] = os.environ.get(prefix + "_action", 'test')

        self.log(str(self.params))

    # ------------------------------------------------------------------------------------------------------------------
    def log_point(self, point, message='\t'):
        self.log('{0:s} ({1:4d},{2:4d}) {3:s} - {4:s} {5}'.format(message, point['x'], point['y'], point['name'],
                                                                  point['plant_stage'], point['meta']))

    # ------------------------------------------------------------------------------------------------------------------
    def is_eligible(self, p):

        if p['pointer_type'].lower() != 'plant': return False
        if p['name'].lower() != self.params['pointname'].lower() and self.params['pointname'] != '*': return False

        # need to search by meta
        if self.params['filter_meta'] != None:
            for t in self.params['filter_meta']:
                key=t[0]
                val = t[1]
                inverse = False
                if val[0] == '!':
                    inverse = True
                    val = val[1:]
                if val.lower() == 'today': val = datetime.date.today().strftime("%B %d, %Y")

                if key == 'plant_stage':
                    if inverse:
                        if p[key] == val: return False
                    else:
                        if p[key] != val: return False
                else:
                    if key in p['meta']:
                        if val!='*':
                            if inverse:
                                if p['meta'][key] == val: return False
                            else:
                                if p['meta'][key] != val: return False
                    else:
                        if not inverse: return False

        return True

    # ------------------------------------------------------------------------------------------------------------------
    def save_meta(self, point):
        if self.params['save_meta'] != None:
            need_update = False

            for t in self.params['save_meta']:
                key=t[0]
                val = t[1]
                if val.lower() == 'today': val = datetime.date.today().strftime("%B %d, %Y")

                # check for special values
                if key == 'del':
                    if val == '*' and point['meta'] != {}:
                        point['meta'] = {}
                        need_update = True
                    else:
                        if val in point['meta']:
                            del point['meta'][val]
                            need_update = True
                else:
                    if (key=='plant_stage'):
                        if point[key]!=val:
                            point[key] = val
                            need_update = True
                    else:
                        if not (key in point['meta'] and point['meta'][key] == val):
                            point['meta'][key] = val
                            need_update = True

            if need_update:
                self.put("points/{}".format(point['id']), point)

    # ------------------------------------------------------------------------------------------------------------------
    def run(self):

        debug = True if self.params['action'] == "test" else False
        points = self.get('points')
        sequences = self.get('sequences')

        # resolve sequence names to ids
        try:
            for s in (
            self.params['sequence']['init'], self.params['sequence']['before'], self.params['sequence']['after'],
            self.params['sequence']['end']):
                if s['name'] != 'None':
                    s['id'] = next(i for i in sequences if i['name'].lower() == s['name'].lower())['id']
        except:
            raise ValueError('Sequence not found: {}'.format(s['name']))

        # filter points
        mypoints = [p for p in points if self.is_eligible(p)]
        print("BEFORE")
        for m in mypoints: self.log_point(m)

        # sort points for optimal movement
        mypoints = sorted(mypoints, key=lambda elem: (int(elem['x']), int(elem['y'])))

        # execute init sequence
        self.execute_sequence(self.params['sequence']['init'], debug)

        # iterate over all eligible points
        for point in mypoints:
            self.execute_sequence(self.params['sequence']['before'], debug)
            if self.params['sequence']['before']['id']!=-1 or self.params['sequence']['after']['id']!=-1:
                self.move_absolute({'x': point['x'], 'y': point['y'], 'z': self.params['default_z']},{'x': 0, 'y': 0, 'z': 0}, debug)
            self.execute_sequence(self.params['sequence']['after'], debug)
            self.save_meta(point)

        # execute end sequence
        self.execute_sequence(self.params['sequence']['end'], debug)
        print("AFTER")
        for m in mypoints: self.log_point(m)


# ----------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":

    try:
        app = MLH()
        app.run()

    except Exception as e:
        try:
            app.log('Something went wrong: {}'.format(str(e)), 'error')
        except:
            print('Something really bad happened: {}.'.format(e))
