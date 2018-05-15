import os
import ast
import datetime
import sys
import requests
from Farmware import *


# inverses boolean expr basing on variable
def invb(inverse, expr):
    if not inverse: return expr
    else: return not expr


class MLH(Farmware):
    def __init__(self):
        Farmware.__init__(self,((__file__.split(os.sep))[len(__file__.split(os.sep)) - 3]).replace('-master', ''))

    # ------------------------------------------------------------------------------------------------------------------
    # loads config parameters
    def load_config(self):
        prefix = self.app_name.lower().replace('-', '_')
        self.args = {}
        self.args['s']={}
        self.args['pointname']     = os.environ.get(prefix + "_pointname", 'Beets')
        self.args['default_z']     = int(os.environ.get(prefix + "_default_z", -300))
        self.args['action']        = os.environ.get(prefix + "_action", 'real')
        self.args['filter_meta']   = os.environ.get(prefix + "_filter_meta", "None")
        self.args['save_meta']     = os.environ.get(prefix + "_save_meta", "[('del','last_watering')]")
        self.args['s']['init']     = os.environ.get(prefix + '_init', 'None')
        self.args['s']['before']   = os.environ.get(prefix + '_before', 'None')
        self.args['s']['after']    = os.environ.get(prefix + '_after', 'None')
        self.args['s']['end']      = os.environ.get(prefix + '_end', 'None')

        try:
            self.args['pointname']=self.args['pointname'].lower().split(',')
            self.args['pointname'] = [x.strip(' ') for x in self.args['pointname']]
            self.args['filter_meta'] = ast.literal_eval(self.args['filter_meta'])
            self.args['save_meta'] = ast.literal_eval(self.args['save_meta'])

            if not isinstance(self.args['filter_meta'], list) and self.args['filter_meta']!=None:
                raise ValueError
            if not isinstance(self.args['save_meta'], list) and self.args['save_meta']!=None:
                raise ValueError
        except:
            raise ValueError("Invalid meta {} or {}".format(self.args['filter_meta'], self.args['save_meta']))
        global tz
        self.device=self.get('device')
        tz=self.device['tz_offset_hrs']

        self.log(str(self.args))

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
                if val.lower() == 'today': val = d2s(today_utc())

                if key == 'plant_stage':
                    if not invb(inverse, p[key] == val): return False
                elif key == 'planted_at':
                    if p['planted_at']==None:
                        if not invb(inverse, val.lower()=='none'): return False
                    dv=d2s(l2d(p['planted_at']))
                    if not invb(inverse, dv == val): return False
                else:
                    if key in p['meta']:
                        if val!='*':
                            if not invb(inverse, p['meta'][key] == val): return False
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
                if val.lower() == 'today': val = d2s(today_utc())

                # check for special values
                if key =='intelligent_watering':
                    continue
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
                            if val == 'planted': p['planted_at'] = d2l(today_utc())
                            need_update = True
                    elif key == 'planted_at':
                        skip=False
                        if p['planted_at']!=None:
                            if d2s(l2d(p['planted_at']))==val: skip=True
                        if not skip:
                            p[key] = d2l(s2d(val))
                            need_update = True
                    elif not (key in p['meta'] and p['meta'][key] == val):
                            p['meta'][key] = val
                            need_update = True

        return need_update

    # ------------------------------------------------------------------------------------------------------------------
    #updates the watering sequence and meta. Returns True if waterign is needed
    def intelligent_watering(self, sequence, p, weather):

        if p['plant_stage'] != 'planted': return False

        # what I believe plants need every day in ml
        #                Name            W1  W2  W3  W4   W5   W6   W7    W8
        watering_needs = {'carrot':     [  50,   50,   50,   50,   50,   50,   50,  50],
                          'beets':      [  50,   50,   50,   50,   50,   50,   50,  50],
                          'zucchini':   [  50,   50,   50,  450,  400,  400,  400,  400],
                          'cabbage':    [  50,   50,   50,  100,  400,  400,  400,  400],
                          'parsley':    [  50,   50,   50,  400,  400,  400,  400,  400],
                          'basil':      [  50,   50,   50,  400,  400,  400,  400,  400],
                          'eggplant':   [  50,   50,   50,  400,  400,  400,  400,  400],
                          'side garden':[3600, 3600, 3600, 3600, 3600, 3600, 3600, 3600]
                          }

        if p['planted_at'] != None:
            planted_at = l2d(p['planted_at'])
            age = (today_utc() - planted_at).days
        else:
            age = 1

        # getting supposed watering for 3 days
        supposed_watering_3 = 0
        actual_watering_3 = 0
        watering_days = {}
        try:
            for i in range(0, 3):
                if (age - i >= 0):
                    supposed_watering_3 += watering_needs[p['name'].lower()][(age - i) / 7]
        except:
            raise ValueError('There is no watering plan for {} for week {}, aborting'.format(p['name'], (age - i) / 7))

        setup=False
        if self.args['save_meta']!=None and ('intelligent_watering','setup') in self.args['save_meta']:
            p['meta']['intelligent_watering'] = '[]'
            setup=True
            ml=supposed_watering_3
        else:
            #getting actual watering
            if 'intelligent_watering' not in p['meta']: p['meta']['intelligent_watering'] = '[]'
            watering_days=dict(map(lambda x: x, ast.literal_eval(p['meta']['intelligent_watering'])))
            watering_days = {k: v for (k, v) in watering_days.items()
                        if today_utc() - s2d(k) < datetime.timedelta(days=7)}
            actual_watering_3=sum(watering_days[k] for k in watering_days.keys()
                        if today_utc() - s2d(k) <datetime.timedelta(days=3))

            # 1 sec or watering is 80ml (in my case)
            ml=int(round(supposed_watering_3-actual_watering_3-self.rain_total_3))

        if ml<0: ml=0
        ms = int(ml / 80.0 * 1000)
        if setup: ms=int(watering_needs[p['name'].lower()][age/7]/ 80.0 * 1000)

        if ml>10:

            #update watering sequence if needed
            if ms > 60000: raise ValueError("Really? more than 1 min of watering of a single plant - check your data!")
            if sequence!=None:
                try:
                    wait = next(x for x in sequence['body'] if x['kind'] == 'wait')
                    if wait['args']['milliseconds']!=ms:
                        wait['args']['milliseconds'] = ms
                        self.log('Updating "{}" with {}ms and syncing ...'.format(sequence['name'],ms))
                        self.put("sequences/{}".format(sequence['id']), sequence)
                        self.sync()
                except:
                    raise ValueError("Update of watering sequence failed")

            #record watering amount into the meta
            today_ls=d2s(today_utc())
            if today_ls not in watering_days: watering_days[today_ls]=ml
            else: watering_days[today_ls]+=ml
            p['meta']['intelligent_watering']=watering_days.items()

            if setup: ml=watering_needs[p['name'].lower()][int(age/7)]
            if sequence != None:
                self.log("{} of age {}w last 3d watering was {}+{}/{}ml -> watering for {}ml({}ms)".
                     format(p['name'], int(age/7), actual_watering_3, self.rain_total_3, supposed_watering_3, ml, ms))

            return True

        self.log("{} of age {}w last 3d watering was {}+{}/{}ml -> watering CANCELLED".
                 format(p['name'], int(age/7), actual_watering_3, self.rain_total_3, supposed_watering_3))
        return False

    # ------------------------------------------------------------------------------------------------------------------
    def to_str(self, p):
        str = '{:s}'.format(p['plant_stage'])
        if p['planted_at'] != None:
            str += '({:s})'.format(d2s(l2d(p['planted_at'])))
        str += ' {}'.format(p['meta'])
        return str

    # ------------------------------------------------------------------------------------------------------------------
    def read_weather(self):
        try:
            wf = open('/tmp/current_weather', 'r')
            weather = ast.literal_eval(wf.read())
            if not isinstance(weather, dict): raise ValueError
            self.log('Weather readings {}'.format(weather))

            self.rain_total_3 = int(round(sum(weather[key]['rain24'] for key in weather.keys()
                                         if (today_utc() - s2d(key)).days < 3) * 10))

            # 1mm of rain is 1000ml of water over 1m2 or 10ml over 10x10sm (under the head)
            self.log('Total rain for last 3 days {}ml over 10x10sm'.format(self.rain_total_3))
        except Exception as e:
            weather = {}
            self.log('No weather information availabe, install Netatmo farmware and run it before this', 'warn')
        return weather

    # ------------------------------------------------------------------------------------------------------------------
    def run(self):
        weather={}

        if self.args['action'] == "test":
            self.log("TEST MODE, NO sequences or movement will be run, meta information will NOT be updated",'warn')
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
        if self.args['save_meta']!=None and ('intelligent_watering', 'setup') in self.args['save_meta']:
            self.log("Setting up intellignet watering, will make a record that you watered last 3 days per schedule",'warn')
            intel_watering = True
        if self.args['s']['after'] != None:
            if 'water' in self.args['s']['after']['name'].lower() and '[mlh]' in self.args['s']['after']['name'].lower():
                if intel_watering: self.log("Will water for today according to the schedule, rain is ignored",'warn')
                intel_watering=True
            else:
                if intel_watering:
                    raise ValueError('Your AFTER sequence is not compatible with intelligent watering'.format(self.args['s']['after']['name'].upper()))

        self.args['s']['side'] = 'None'
        if intel_watering:
            self.log("Intelligent watering mode is engaged",'warn')
            weather=self.read_weather()
            try: self.args['s']['side']=next(i for i in all_s if i['name'].lower() == 'Water [MLH] Side Garden'.lower())
            except: pass

        # execute init sequence
        self.execute_sequence(self.args['s']['init'], 'INIT: ')

        # iterate over all eligible points
        for plant in points:
            need_update=False
            message = 'Plant: ({:4d},{:4d}) {:15s} - {:s}'.format(plant['x'], plant['y'], plant['name'],self.to_str(plant))

            sq = self.args['s']['after']
            if intel_watering:
                if plant['name'].lower() == 'side garden': sq=self.args['s']['side']
                if self.intelligent_watering(sq, plant, weather):
                    need_update=True

            if not intel_watering or need_update:
                self.execute_sequence(self.args['s']['before'], 'BEFORE: ')

                if self.args['s']['before']!=None or self.args['s']['after']!=None:
                        if plant['name'].lower()!='side garden':
                            self.move_absolute({'x': plant['x'], 'y': plant['y'], 'z': self.args['default_z']})

                self.execute_sequence(sq, 'AFTER: ')

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
        app.log('HTTP error {} {} '.format(error.response.status_code,error.response.text[0:100]), 'error')
    except Exception as e:
        app.log('Something went wrong: {}'.format(str(e)), 'error')
    sys.exit(1)
