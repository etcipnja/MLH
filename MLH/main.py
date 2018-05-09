import os
import ast
import datetime
import sys
import requests
import json
from Farmware import Farmware

class MLH(Farmware):
    def __init__(self):
        Farmware.__init__(self,((__file__.split(os.sep))[len(__file__.split(os.sep)) - 3]).replace('-master', ''))

    # ------------------------------------------------------------------------------------------------------------------
    def load_config(self):
        prefix = self.app_name.lower().replace('-', '_')
        self.p = {}
        self.p['s']={}
        self.p['pointname']     = os.environ.get(prefix + "_pointname", '*').lower().replace(' ','').split(',')
        self.p['default_z']     = int(os.environ.get(prefix + "_default_z", -300))
        self.p['action']        = os.environ.get(prefix + "_action", 'test')
        self.p['filter_meta']   = os.environ.get(prefix + "_filter_meta", 'None')
        self.p['save_meta']     = os.environ.get(prefix + "_save_meta", "None")
        self.p['s']['init']     = os.environ.get(prefix + '_init', 'None')
        self.p['s']['before']   = os.environ.get(prefix + '_before', 'None')
        self.p['s']['after']    = os.environ.get(prefix + '_after', 'Water [MLH]')
        self.p['s']['end']      = os.environ.get(prefix + '_end', 'None')

        try:
            self.p['filter_meta'] = ast.literal_eval(self.p['filter_meta'])
            self.p['save_meta'] = ast.literal_eval(self.p['save_meta'])

            if not isinstance(self.p['filter_meta'], list) and self.p['filter_meta']!=None:
                raise ValueError
            if not isinstance(self.p['save_meta'], list) and self.p['save_meta']!=None:
                raise ValueError
        except:
            raise ValueError("Invalid meta {} or {}".format(self.p['filter_meta'], self.p['save_meta']))

        self.log(str(self.p))

     # ------------------------------------------------------------------------------------------------------------------
    def is_eligible_point(self, p):

        if p['pointer_type'].lower() != 'plant': return False
        if p['name'].lower() not in self.p['pointname'] and '*' not in self.p['pointname']: return False

        # need to search by meta
        if self.p['filter_meta'] != None:
            for t in self.p['filter_meta']:
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
                elif key == 'planted_at':
                    if p['planted_at']==None:
                        if inverse: return val.lower()!='none'
                        else: return val.lower()=='none'
                    d = datetime.datetime.strptime(p['planted_at'], "%Y-%m-%dT%H:%M:%S.%fZ").date()
                    dv=d.strftime("%B %d, %Y")
                    if inverse:
                        if dv == val: return False
                    else:
                        if dv != val: return False
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
    def save_meta(self, point, debug):
        if self.p['save_meta'] != None:
            need_update = False

            for t in self.p['save_meta']:
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
                    if key=='plant_stage':
                        if point[key]!=val:
                            point[key] = val
                            if val=='planned': point['planted_at']=None
                            if val == 'planted': point['planted_at'] = datetime.date.today().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                            need_update = True
                    elif key == 'planted_at':
                        skip=False
                        if point['planted_at']!=None:
                            d = datetime.datetime.strptime(point['planted_at'], "%Y-%m-%dT%H:%M:%S.%fZ").date()
                            dv = d.strftime("%B %d, %Y")
                            if dv==val: skip=True
                        if not skip:
                            d = datetime.datetime.strptime(val, "%B %d, %Y").date()
                            dv = d.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                            point[key] = dv
                            need_update = True
                    elif not (key in point['meta'] and point['meta'][key] == val):
                            point['meta'][key] = val
                            need_update = True

            if need_update and not debug:
                self.put("points/{}".format(point['id']), point)

            return need_update

    # ------------------------------------------------------------------------------------------------------------------
    def prepare_sequence(self, sequence, plant, weather, debug):

        if plant['plant_stage'] != 'planted': return False

        age=1 #default age
        if plant['planted_at']!=None:
            planted_at=datetime.datetime.strptime(plant['planted_at'], "%Y-%m-%dT%H:%M:%S.%fZ").date()
            age=(datetime.datetime.now().date()-planted_at).days

        rain_total_3=sum(weather[key]['rain24'] for key in weather.keys()
                         if (datetime.date.today()-datetime.datetime.strptime(key, "%B %d, %Y").date()).days<3)

        # 1mm of rain is 1000ml of water over 1m2 or 10ml over 10x10sm (under the head)
        # 1 sec or watering is 80ml

        #what I believe plants need every day
        watering_needs={'Carrot':   [50, 50, 50, 50,  50],
                        'Beets':    [50, 50, 50, 50,  50],
                        'Zucchini': [50, 50, 50, 450, 400, 400, 400, 400],
                        'Cabbage':  [50, 50, 50, 100, 150],
                        'Parsley':  [50, 50, 50, 400, 400, 400, 400, 400]
                        }

        supposed_watering_3=0
        try:
            for i in (int((age-3)/7),int((age-2)/7),int((age-1)/7)):
                supposed_watering_3+=watering_needs[plant['name']][int((age-i)/7)]
        except:
            raise ValueError('There is no watering plan for {}, aborting'.format(plant['name']))

        water_today=watering_needs[plant['name']][int(age/7)]
        ms=int(water_today/80.0*1000)

        self.log("Intelligent watering of {} {} days old for {}ml or {}ms".format(plant['name'],age,water_today,ms))
        try:
            duration=ms
            wait = next(x for x in sequence['body'] if x['kind'] == 'wait')
            if wait['args']['milliseconds']!=duration:
                wait['args']['milliseconds'] = duration
                self.log('Updating "{}" with {}ms and syncing ...'.format(sequence['name'],duration))
                if not debug: self.put("sequences/{}".format(sequence['id']), sequence)
                self.sync()
        except:
            raise ValueError("Update of watering sequence failed")

        return True

    # ------------------------------------------------------------------------------------------------------------------
    def to_str(self, point):
        str = '{:s}'.format(point['plant_stage'])
        if point['plant_stage']=='planted' and point['planted_at'] != None:
            d = datetime.datetime.strptime(point['planted_at'], "%Y-%m-%dT%H:%M:%S.%fZ").date()
            str += '({})'.format(d.strftime("%B %d, %Y"))
        str += ' {}'.format(point['meta'])
        return str

    # ------------------------------------------------------------------------------------------------------------------
    def run(self):

        debug = False
        if self.p['action'] == "test":
            self.log("TEST MODE, no sequences or movement will be run, meta information will NOT be updated",'warn')
            debug=True

        #processing points
        points = self.get('points')
        # filter points
        points = [p for p in points if self.is_eligible_point(p)]
        if len(points) == 0:
            raise ValueError('No plants selected by the filter, aborting')

        self.log('{} plants selected by the filter'.format(len(points)), 'success')
        points = sorted(points, key=lambda elem: ( elem['name'], int(elem['x']), int(elem['y'])))

        #processing sequences
        all_s = self.get('sequences')
        try:
            for k in self.p['s']:
                if self.p['s'][k].lower()=='none': self.p['s'][k]=None
                else: self.p['s'][k]=next(i for i in all_s if i['name'].lower() == self.p['s'][k].lower())
        except:
            raise ValueError('Sequence not found: {}'.format(self.p['s'][k].upper()))

        #check if we need to enable intelligent watering
        intel_watering=False
        if self.p['s']['after']!=None:
            if 'water' in self.p['s']['after']['name'].lower() and '[mlh]' in  self.p['s']['after']['name'].lower():
                try:
                    wf = open('/tmp/current_weather', 'r')
                    weather = ast.literal_eval(wf.read())
                    if not isinstance(weather, dict): raise ValueError
                    self.log('Current weather {}'.format(weather))
                    intel_watering = True
                except Exception as e:
                    weather = {}
                    self.log('No weather information availabe, consider installing Netatmo farmware and run it before this',
                             'warn')

        # execute init sequence
        self.execute_sequence(self.p['s']['init'], debug, 'INIT: ')

        # iterate over all eligible points
        for point in points:
            message = 'Plant: ({:4d},{:4d}) {:s} - {:s}'.format(point['x'], point['y'], point['name'],self.to_str(point))
            skip=False
            if intel_watering and point['plant_stage']!='planted': skip=True
            if not skip:
                self.execute_sequence(self.p['s']['before'], debug, 'BEFORE: ')
                if self.p['s']['before']!=None or self.p['s']['after']!=None:
                    self.move_absolute({'x': point['x'], 'y': point['y'], 'z': self.p['default_z']},{'x': 0, 'y': 0, 'z': 0}, debug)
                if intel_watering:
                    self.prepare_sequence(self.p['s']['after'],point, weather, debug)
                self.execute_sequence(self.p['s']['after'], debug, 'AFTER: ')
            else: message='SKIPPED-AS-NON-PLANTED: '+message
            if self.save_meta(point, debug):
                message+=' -> {}'.format(self.to_str(point))
            self.log(message)

        # execute end sequence
        self.execute_sequence(self.p['s']['end'], debug, "END: ")


# ----------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":

    try:
        app = MLH()
        app.load_config()
        app.run()
        sys.exit(0)

    except requests.exceptions.HTTPError as error:
        app.log('HTTP error {} {} '.format(error.response.status_code,error.response.text), 'error')
    except Exception as e:
        app.log('Something went wrong: {}'.format(str(e)), 'error')
    sys.exit(1)
