import os
import ast
import datetime
import sys
import requests
from Farmware import Farmware
import calendar


class MLH(Farmware):
    def __init__(self):
        Farmware.__init__(self,((__file__.split(os.sep))[len(__file__.split(os.sep)) - 3]).replace('-master', ''))

    # ------------------------------------------------------------------------------------------------------------------
    # loads config parameters
    def load_config(self):
        prefix = self.app_name.lower().replace('-', '_')
        self.args = {}
        self.args['s']={}
        self.args['pointname']     = os.environ.get(prefix + "_pointname", '*')
        self.args['default_z']     = int(os.environ.get(prefix + "_default_z", -300))
        self.args['action']        = os.environ.get(prefix + "_action", 'test')
        self.args['filter_meta']   = os.environ.get(prefix + "_filter_meta", "None")
        self.args['save_meta']     = os.environ.get(prefix + "_save_meta", "None")
        self.args['s']['init']     = os.environ.get(prefix + '_init', 'None')
        self.args['s']['before']   = os.environ.get(prefix + '_before', 'None')
        self.args['s']['after']    = os.environ.get(prefix + '_after', 'Water [MLH]')
        self.args['s']['end']      = os.environ.get(prefix + '_end', 'None')

        try:
            self.args['pointname']=self.args['pointname'].lower().replace(' ', '').split(',')
            self.args['filter_meta'] = ast.literal_eval(self.args['filter_meta'])
            self.args['save_meta'] = ast.literal_eval(self.args['save_meta'])

            if not isinstance(self.args['filter_meta'], list) and self.args['filter_meta']!=None:
                raise ValueError
            if not isinstance(self.args['save_meta'], list) and self.args['save_meta']!=None:
                raise ValueError
        except:
            raise ValueError("Invalid meta {} or {}".format(self.args['filter_meta'], self.args['save_meta']))

        self.log(str(self.args))

    #------------------------------------------------------------------------------------------------------------------
    def utc_to_local(self, utc_dt):
        # get integer timestamp to avoid precision lost
        timestamp = calendar.timegm(utc_dt.timetuple())
        local_dt = datetime.fromtimestamp(timestamp)
        assert utc_dt.resolution >= timedelta(microseconds=1)
        return local_dt.replace(microsecond=utc_dt.microsecond)
    # ------------------------------------------------------------------------------------------------------------------
    # Converts UTC date represented by a string into local date represented by a string
    def u2l(self, utc_s):
        d = datetime.datetime.strptime(utc_s, "%Y-%m-%dT%H:%M:%S.%fZ")
        d=self.utc_to_local(d)
        local_s = d.strftime("%B %d, %Y")
        return local_s

    # ------------------------------------------------------------------------------------------------------------------
    # Converts local date represented by a string into UTC date represented by a string
    def l2u(self, local_s=''):
        if local_s.lower()=='none': return None
        if local_s!='':
            d = datetime.datetime.strptime(local_s, "%B %d, %Y")
        else:
            d=datetime.date.today()
        d = d.replace(tzinfo=tz.tzlocal())
        d = d.astimezone(tz.tzutc())
        local_s = d.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        return local_s

    # ------------------------------------------------------------------------------------------------------------------
    # inverses boolean expr basing on variable
    def invb(self, inverse, expr):
        if not inverse: return expr
        else: return not expr

    # ------------------------------------------------------------------------------------------------------------------
    # returns true if point is matching filtering criteria
    def is_eligible_point(self, p):

        if p['pointer_type'].lower() != 'plant': return False
        if p['name'].lower() not in self.args['pointname'] and '*' not in self.args['pointname']: return False

        # need to search by meta
        if self.args['filter_meta'] != None:
            for t in self.args['filter_meta']:
                key=t[0]
                val = t[1]
                inverse = False
                if val[0] == '!':
                    inverse = True
                    val = val[1:]
                if val.lower() == 'today': val = datetime.date.today().strftime("%B %d, %Y")

                if key == 'plant_stage':
                    if not self.invb(inverse, p[key] == val): return False
                elif key == 'planted_at':
                    if p['planted_at']==None:
                        if not self.invb(inverse, val.lower()=='none'): return False
                    dv=self.u2l(p['planted_at'])
                    if not self.invb(inverse, dv == val): return False
                else:
                    if key in p['meta']:
                        if val!='*':
                            if not self.invb(inverse, p['meta'][key] == val): return False
                    else:
                        if not inverse: return False

        return True

    # ------------------------------------------------------------------------------------------------------------------
    # update metadata
    def update_meta(self, p):

        need_update = False
        if self.args['save_meta'] != None:
            for t in self.args['save_meta']:
                key=t[0]
                val = t[1]
                if val.lower() == 'today': val = datetime.date.today().strftime("%B %d, %Y")

                # check for special values
                if key == 'del':
                    if val == '*' and p['meta'] != {}:
                        p['meta'] = {}
                        need_update = True
                    else:
                        if val in p['meta']:
                            del p['meta'][val]
                            need_update = True
                else:
                    if key=='plant_stage':
                        if p[key]!=val:
                            p[key] = val
                            if val=='planned': p['planted_at']=None
                            if val == 'planted': p['planted_at'] = self.l2u()
                            need_update = True
                    elif key == 'planted_at':
                        skip=False
                        if p['planted_at']!=None:
                            if self.u2l(p['planted_at'])==val: skip=True
                        if not skip:
                            p[key] = self.l2u(val)
                            need_update = True
                    elif not (key in p['meta'] and p['meta'][key] == val):
                            p['meta'][key] = val
                            need_update = True

        return need_update

    # ------------------------------------------------------------------------------------------------------------------
    def intelligent_watering(self, sequence, p, weather):

        if p['plant_stage'] != 'planted': return False

        age=1 #default age
        if p['planted_at']!=None:
            planted_at=datetime.datetime.strptime(p['planted_at'], "%Y-%m-%dT%H:%M:%S.%fZ").date()
            age=(datetime.datetime.now().date()-planted_at).days

        rain_total_3=sum(weather[key]['rain24'] for key in weather.keys()
                         if (datetime.date.today()-datetime.datetime.strptime(key, "%B %d, %Y").date()).days<3)

        # 1mm of rain is 1000ml of water over 1m2 or 10ml over 10x10sm (under the head)
        # 1 sec or watering is 80ml (in my case)

        #what I believe plants need every day in ml
        #                Name        W1  W2  W3  W4   W5   W6   W7    W8
        watering_needs={'Carrot':   [50, 50, 50, 50,  50,  50,  50,   50],
                        'Beets':    [50, 50, 50, 50,  50,  50,  50,   50],
                        'Zucchini': [50, 50, 50, 450, 400, 400, 400, 400],
                        'Cabbage':  [50, 50, 50, 100, 400, 400, 400, 400],
                        'Parsley':  [50, 50, 50, 400, 400, 400, 400, 400]
                        }

        supposed_watering_3=0
        try:
            for i in (int((age-3)/7),int((age-2)/7),int((age-1)/7)):
                supposed_watering_3+=watering_needs[p['name']][int((age - i) / 7)]
        except:
            raise ValueError('There is no watering plan for {}, aborting'.format(p['name']))

        ml=watering_needs[p['name']][int(age / 7)]
        ms=int(ml/80.0*1000)

        self.log("Intelligent watering of {} {} days old for {}ml or {}ms".format(p['name'], age, ml, ms))

        #update watering sequence if needed
        try:
            duration=ms
            wait = next(x for x in sequence['body'] if x['kind'] == 'wait')
            if wait['args']['milliseconds']!=duration:
                wait['args']['milliseconds'] = duration
                self.log('Updating "{}" with {}ms and syncing ...'.format(sequence['name'],duration))
                self.put("sequences/{}".format(sequence['id']), sequence)
                self.sync()
        except:
            raise ValueError("Update of watering sequence failed")

        #record watering amount into the meta
        if 'intelligent_watering' not in p['meta']: p['meta']['intelligent_watering']={}
        p['meta']['intelligent_watering'][datetime.date.today().strftime("%B %d, %Y")]=ml

        return True

    # ------------------------------------------------------------------------------------------------------------------
    def to_str(self, p):
        str = '{:s}'.format(p['plant_stage'])
        if p['planted_at'] != None:
            str += '({:15s})'.format(self.u2l(p['planted_at']))
        str += ' {}'.format(p['meta'])
        return str

    # ------------------------------------------------------------------------------------------------------------------
    def run(self):

        if self.args['action'] == "test":
            self.log("TEST MODE, no sequences or movement will be run, meta information will NOT be updated",'warn')
            self.debug=True

        #processing points
        points = self.get('points')
        # filter points
        points = [x for x in points if self.is_eligible_point(x)]
        if len(points) == 0:
            self.log('No plants selected by the filter, aborting','warn')
            return

        self.log('{} plants selected by the filter'.format(len(points)), 'success')
        points = sorted(points, key=lambda elem: ( elem['name'], int(elem['x']), int(elem['y'])))

        #processing sequences
        all_s = self.get('sequences')
        try:
            for k in self.args['s']:
                if self.args['s'][k].lower()== 'none': self.args['s'][k]=None
                else: self.args['s'][k]=next(i for i in all_s if i['name'].lower() == self.args['s'][k].lower())
        except:
            raise ValueError('Sequence not found: {}'.format(self.args['s'][k].upper()))

        #check if we need to enable intelligent watering
        intel_watering=False
        weather={}
        if self.args['s']['after']!=None:
            if 'water' in self.args['s']['after']['name'].lower() and '[mlh]' in self.args['s']['after']['name'].lower():
                try:
                    wf = open('/tmp/current_weather', 'r')
                    weather = ast.literal_eval(wf.read())
                    if not isinstance(weather, dict): raise ValueError
                    self.log('Weather readings {}'.format(weather))
                    intel_watering = True
                except Exception as e:
                    weather = {}
                    self.log('No weather information availabe, install Netatmo farmware and run it before this','warn')

        # execute init sequence
        self.execute_sequence(self.args['s']['init'], 'INIT: ')

        # iterate over all eligible points
        for plant in points:
            need_update = False
            message = 'Plant: ({:4d},{:4d}) {:15s} - {:s}'.format(plant['x'], plant['y'], plant['name'],self.to_str(plant))
            if not intel_watering or plant['plant_stage']=='planted':
                self.execute_sequence(self.args['s']['before'], 'BEFORE: ')
                if self.args['s']['before']!=None or self.args['s']['after']!=None:
                    self.move_absolute({'x': plant['x'], 'y': plant['y'], 'z': self.args['default_z']})
                if intel_watering:
                    if self.intelligent_watering(self.args['s']['after'], plant, weather): need_update=True
                self.execute_sequence(self.args['s']['after'], 'AFTER: ')
            else: message='SKIPPED-AS-NON-PLANTED: '+message
            if self.update_meta(plant): need_update=True

            if need_update:
                message += ' -> {}'.format(self.to_str(plant))
                self.put("points/{}".format(plant['id']), plant)

            self.log(message)

        # execute end sequence
        self.execute_sequence(self.args['s']['end'], "END: ")


# ----------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":

    app = MLH()
    try:
        app.load_config()
        app.run()
        sys.exit(0)

    except NameError as error:
        app.log('SYNTAX!: {}'.format(str(error)), 'error')
        raise
    except requests.exceptions.HTTPError as error:
        app.log('HTTP error {} {} '.format(error.response.status_code,error.response.text), 'error')
    except Exception as e:
        app.log('Something went wrong: {}'.format(str(e)), 'error')
    sys.exit(1)
