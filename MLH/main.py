import time
from Farmware import *

# inverses boolean expr basing on variable
def invb(inverse, expr):
    if not inverse: return expr
    else: return not expr


class MLH(Farmware):
    def __init__(self):
        Farmware.__init__(self,((__file__.split(os.sep))[len(__file__.split(os.sep)) - 3]).replace('-master', '').replace('-dev',''))

    # ------------------------------------------------------------------------------------------------------------------
    # loads config parameters
    def load_config(self):

        super(MLH,self).load_config()
        self.get_arg('action'       , "real")
        self.get_arg('pointname'    , "*")
        self.get_arg('default_z'    , -400)
        self.get_arg('filter_meta'  , "None")
        self.get_arg('save_meta'    , "None")
        self.get_arg('init'         , "None")
        self.get_arg('before'       , "None")
        self.get_arg('after'        , "Water [MLH]")
        self.get_arg('end'          , "None")

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
                if val.lower() == 'today': val = d2s(today_local())

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
                if val.lower() == 'today': val = d2s(today_local())

                # check for special values
                if key =='iwatering':
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
                            if val=='planned': p['planted_at']= "1980-01-01T00:00:00.000Z"
                            if val == 'planted': p['planted_at'] = d2l(today_utc())
                            need_update = True
                    elif key == 'planted_at':
                        skip=False
                        if p['planted_at']!=None:
                            if d2s(u2l(l2d(p['planted_at'])))==val: skip=True
                        if not skip:
                            p[key] = d2l(l2u(s2d(val)))
                            need_update = True
                    elif not (key in p['meta'] and p['meta'][key] == val):
                            p['meta'][key] = val
                            need_update = True

        return need_update

    # ------------------------------------------------------------------------------------------------------------------
    # retrun supposed watering for the plant with the given spread and age
    # CHANGE HERE to fullfill your assumptions!!!
    def get_supposed_watering(self, max_d, age):
        min_d=2
        step=max_d/(7*10.0) #I believe in 10 weeks after seeding the plant takes max area
        d=step*age
        if d<min_d: r=min_d
        if d>max_d: r=max_d
        return int(d*4)     #Magic multiplier that converts adjuseted diameter to ml

    # ------------------------------------------------------------------------------------------------------------------
    def get_travel_height(self, p, def_z):
        min_h=20
        max_h=p['meta']['height']
        age=self.plant_age(p)
        step=max_h/(7*10.0) #I believe in 10 weeks after seeding the plant takes max height
        h=step*age
        if h<min_h: r=min_h
        if h>max_h: r=max_h
        h=def_z+h
        if def_z<0 and h>0: h=0
        return int(h)
    # ------------------------------------------------------------------------------------------------------------------
    #updates the watering sequence and meta. Returns True if waterign is needed
    def iwatering(self, sequence, p, skip):

        age = self.plant_age(p)
        if age==0: return False

        save = False
        today_ls = d2s(today_local())

        if 'height' not in p['meta'] or 'spread' not in p['meta']:
            if p['name'].lower() == 'side garden':
                p['meta']['spread'] = 300 * 6
                p['meta']['height'] = 100
            else:
                a=self.lookup_openfarm(p)['data'][0]['attributes']
                p['meta']['spread'] = a['spread'] * 10
                p['meta']['height'] = a['height'] * 10
        else:
            p['meta']['spread']=int(p['meta']['spread'])
            p['meta']['height']=int(p['meta']['height'])


        #calculating supposed watering for today
        supposed_watering = self.get_supposed_watering(p['meta']['spread'],age)

        #calculating actual_watering today
        actual_watering=0
        watering_days={}
        if 'iwatering' in p['meta']:
            watering_days=ast.literal_eval(p['meta']['iwatering'])
        if today_ls in watering_days:
            actual_watering = watering_days[today_ls]
        else: watering_days[today_ls]=0

        #how much to water in ml
        ml = int(round(supposed_watering - actual_watering)) if supposed_watering>actual_watering else 0
        ms = int(ml / 80.0 * 1000)  #in my case watering nozzle produce 80ml in a sec

        if ml>0:
            #update watering sequence if needed
            #if ms > 120000: raise ValueError("Really? more than 1 min of watering of a single plant - check your data!")
            if sequence!=None and not skip:

                self.log("{} of age {}d watering was {}/{}ml -> watering for {}ml({}ms)".
                         format(p['name'], age, actual_watering, supposed_watering, ml, ms))

                try:
                    wait = next(x for x in sequence['body'] if x['kind'] == 'wait')
                    if wait['args']['milliseconds']!=ms:
                        wait['args']['milliseconds'] = ms
                        self.log('Updating "{}" with {}ms and syncing ...'.format(sequence['name'],ms))
                        self.put("sequences/{}".format(sequence['id']), sequence)
                        time.sleep(5)
                        self.sync()
                except:
                    if p['name'].lower()!='side garden':
                        raise ValueError("Update of watering sequence {} failed".format(sequence['name'].upper()))

            #record watering amount into the meta
            if not skip:
                watering_days[today_ls]+=ml
                p['meta']['iwatering']=str(watering_days)
                save=True

        return save


    # ------------------------------------------------------------------------------------------------------------------
    def to_str(self, p):
        str = '{:s}'.format(p['plant_stage'])
        if p['planted_at'] != None:
            str += '({:s})'.format(d2s(u2l(l2d(p['planted_at']))))
        str += ' {}'.format(p['meta'])
        return str

    # ------------------------------------------------------------------------------------------------------------------
    # returns True if iWatering shall be enabled
    def is_iwatering(self):

        iwatering = False
        if self.args['after'] != None:
            if 'water' in self.args['after']['name'].lower() and '[mlh]' in self.args['after']['name'].lower():
                self.log("iWatering mode is engaged", 'warn')
                iwatering = True
                self.args['side'] = 'None'
                try:
                    self.args['side'] = next(i for i in self.sequences() if i['name'].lower() =='Water [MLH] Side Garden'.lower())
                except: pass

        return iwatering

    # ------------------------------------------------------------------------------------------------------------------
    # returns True if it is recommended to skip watering today
    def check_weather(self):

        self.load_weather()
        self.log('Weather: {}'.format(self.weather))
        # checking for the recent rain
        today = d2s(today_local())
        if today in self.weather:
            if self.weather[today]['rain24'] > 1:  # small rain
                self.log("Skipping watering due to rain today {}mm".format(self.weather[today]['rain24']), 'warn')
                return True

        yesterday = d2s(today_local() - datetime.timedelta(days=1))
        if yesterday in self.weather:
            if self.weather[yesterday]['rain24'] > 10:  # medium rain
                self.log("Skipping watering due to medium or heavy rain yesterday {}mm".format(self.weather[yesterday]['rain24']), 'warn')
                return True
        twodaysago = d2s(today_local() - datetime.timedelta(days=2))
        if twodaysago in self.weather:
            if self.weather[twodaysago]['rain24'] > 20:  # heavy rain
                self.log("Skipping watering due to heavy rain 2 days ago {}mm".format(self.weather[twodaysago]['rain24']), 'warn')
                return True

        return False
    # ------------------------------------------------------------------------------------------------------------------
    def run(self):

        #processing points
        plants = [x for x in self.points() if self.is_eligible_point(x)]
        if len(plants) == 0:
            self.log('No plants selected by the filter, aborting','warn')
            return

        self.log('{} plants selected by the filter'.format(len(plants)), 'success')
        plants = sorted(plants, key=lambda elem: ( elem['name'], int(elem['x']), int(elem['y'])))

        #processing sequences
        try:
            for k in ('init','before','after','end'):
                if self.args[k].lower()== 'none': self.args[k]=None
                else: self.args[k]=next(i for i in self.sequences() if i['name'].lower() == self.args[k].lower())
        except:
            raise ValueError('Sequence not found: {}'.format(self.args[k].upper()))

        #check if we need to enable iWatering
        iw=self.is_iwatering()
        skip=self.check_weather() if iw else False

        # execute init sequence
        self.execute_sequence(self.args['init'], 'INIT: ')

        # iterate over all eligible plants
        for plant in plants:
            need_update=False
            message = 'Plant: ({:4d},{:4d}) {:15s} - {:s}'.format(plant['x'], plant['y'], plant['name'],self.to_str(plant))

            travel_height=self.args['default_z']
            sq = self.args['after']
            if iw:
                if plant['name'].lower() == 'side garden': sq=self.args['side']
                if self.iwatering(sq, plant, skip):
                    travel_height = self.get_travel_height(plant,self.args['default_z'])
                    need_update=True

            if not iw or need_update:
                self.execute_sequence(self.args['before'], 'BEFORE: ')
                if self.args['before']!=None or self.args['after']!=None:
                        if plant['name'].lower()!='side garden' and not skip:
                            self.move_absolute({'x': plant['x'], 'y': plant['y'], 'z': travel_height})

                if not skip: self.execute_sequence(sq, 'AFTER: ')

            if self.update_meta(plant): need_update=True

            if need_update:
                message += ' -> {}'.format(self.to_str(plant))
                self.put("points/{}".format(plant['id']), plant)

            self.log(message)

        # execute end sequence
        self.execute_sequence(self.args['end'], "END: ")


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
