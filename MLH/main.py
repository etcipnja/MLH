from Farmware import *

# inverses boolean expr basing on variable
def invb(inverse, expr):
    if not inverse: return expr
    else: return not expr


class MLH(Farmware):
    def __init__(self):
        Farmware.__init__(self,((__file__.split(os.sep))[len(__file__.split(os.sep)) - 3]).replace('-master', '').replace('-dev',''))
        self.chain_sequence = None

    # ------------------------------------------------------------------------------------------------------------------
    # loads config parameters
    def load_config(self):

        #ASSUMPTIONS - CHANGE HERE TO ADJUST TO YOUR CASE
        self.ml_per_sec=80.0    #my pump produces 80ml/sec
        self.coming_of_age=7*15 #I believe that in 15 weeks plant becomes an adult (i.e. takes the full height and spread)
        self.magic_d2lm=3       #Magic mutiplier to convert plant size to ml needed for watering
        self.small_rain=1       #1mm is a small rain (cancells watering today)
        self.medium_rain=10     #10mm is a medium rain (cancells watering today and tomorrow)
        self.big_rain=20        #20mm is a big rain (cancells watering today, tomorrow and day after tomorrow)


        super(MLH,self).load_config()
        self.get_arg('action'       , "test", str)
        self.get_arg('pointname'    , '*', str)
        self.get_arg('default_z'    , 0, int)
        self.get_arg('filter_meta'  , None, list)
        self.get_arg('save_meta'    , None,list)
        self.get_arg('init'         , None, str)
        self.get_arg('before'       , None, str)
        self.get_arg('after'        , 'Water [MLH]', str)
        self.get_arg('end'          , None, str)

        self.args['pointname']=self.args['pointname'].lower().split(',')
        self.args['pointname'] = [x.strip(' ') for x in self.args['pointname']]

        self.log(str(self.args))

    # ------------------------------------------------------------------------------------------------------------------
    # returns true if point is matching filtering criteria
    def is_eligible_point(self, p):

        if p['pointer_type'].lower() != 'plant': return False
        inv=False
        if '*' not in self.args['pointname']:
            if '!' in self.args['pointname']: inv=True
            if inv:
                if p['name'].lower() in self.args['pointname']: return False
            else:
                if p['name'].lower() not in self.args['pointname']: return False

        # need to search by meta
        if self.args['filter_meta'] is not None:
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
                    if p['planted_at'] is None:
                        if not invb(inverse, val.lower()=='none'): return False
                    planted=p['planted_at'] if p['planted_at'] is not None else "1980-01-01T00:00:00.000Z"
                    dv=d2s(l2d(planted))
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
        if self.args['save_meta'] is not None:
            for t in self.args['save_meta']:
                key=t[0]
                val = t[1]
                if val.lower() == 'today': val = d2s(today_local())

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
                            if val=='planned': p['planted_at']= "1980-01-01T00:00:00.000Z"
                            if val == 'planted': p['planted_at'] = d2l(today_utc())
                            need_update = True
                    elif key == 'planted_at':
                        skip=False
                        if p['planted_at'] is not None:
                            if d2s(u2l(l2d(p['planted_at'])))==val: skip=True
                        if not skip:
                            p[key] = d2l(l2u(s2d(val)))
                            need_update = True
                    elif key == 'iwatering':
                        iwatering=ast.literal_eval(p['meta']['iwatering'])
                        if iwatering.pop(val, None):
                            p['meta']['iwatering'] = str(iwatering)
                            need_update = True
                    elif not (key in p['meta'] and p['meta'][key] == val):
                            p['meta'][key] = val
                            need_update = True

        return need_update

    # ------------------------------------------------------------------------------------------------------------------
    # return supposed watering for the plant with the given spread and age
    def get_supposed_watering(self, max_d, age):
        min_d=2
        step=max_d/float(self.coming_of_age)
        d=step*age
        if d<min_d: r=min_d
        if d>max_d: r=max_d
        return int(d*self.magic_d2lm)

    # ------------------------------------------------------------------------------------------------------------------
    def get_travel_height(self, p, def_z):
        min_h=0
        max_h=int(p['meta']['height'])
        age=self.plant_age(p)
        step=max_h/float(self.coming_of_age)
        h=step*age
        if h<min_h: r=min_h
        if h>max_h: r=max_h
        h=def_z+h
        if def_z<0 and h>0: h=0
        return int(h)
    # ------------------------------------------------------------------------------------------------------------------
    #updates the watering sequence and meta. Returns True if waterign is needed
    def do_iwatering(self, sequence, p):

        age = self.plant_age(p)
        if age==0: return False

        save = False
        today_ls = d2s(today_local())

        if 'height' not in p['meta'] or 'spread' not in p['meta']:
            try:
                a=self.lookup_openfarm(p)['data'][0]['attributes']
                p['meta']['spread'] = a['spread'] * 10
                p['meta']['height'] = a['height'] * 10
            except:
                self.log("Open farm doesn't seem to know about {}, consider creating dedicated sequence".format(p['name']))
                p['meta']['spread'] = 5
                p['meta']['height'] = 5
        else:
            p['meta']['spread']=int(p['meta']['spread'])
            p['meta']['height']=int(p['meta']['height'])


        #calculating supposed watering for today
        supposed_watering = self.get_supposed_watering(p['meta']['spread'],age)

        #calculating actual_watering today
        actual_watering=0
        watering_days=self.get_watering_days(p)
        if today_ls in watering_days:
            actual_watering = watering_days[today_ls]
        else: watering_days[today_ls]=0

        #how much to water in ml
        ml = int(round(supposed_watering - actual_watering)) if supposed_watering>1.2*actual_watering else 0
        ms = int(ml / self.ml_per_sec * 1000)

        if ml>0:
            #update watering sequence if needed
            if sequence!=None:

                self.log("{} of age {}d watering was {}/{}ml -> watering for {}ml({}ms)".
                         format(p['name'], age, actual_watering, supposed_watering, ml, ms))

                try:
                    wait = next(x for x in sequence['body'] if x['kind'] == 'wait')
                    if wait['args']['milliseconds']!=ms:
                        wait['args']['milliseconds'] = ms
                        self.log('Updating "{}" with {}ms and syncing ...'.format(sequence['name'],ms))
                        self.put("sequences/{}".format(sequence['id']), sequence)
                        self.sync()
                except:
                    raise ValueError("Update of watering sequence {} failed".format(sequence['name'].upper()))

            #record watering amount into the meta
            watering_days[today_ls]+=ml
            p['meta']['iwatering']=str(watering_days)
            save=True

        return save


    # ------------------------------------------------------------------------------------------------------------------
    def finalize_log(self, p):
        out = '{:s}'.format(p['plant_stage'])
        if p['planted_at'] != None:
            out += '({:s})'.format(d2s(u2l(l2d(p['planted_at']))))
        if 'iwatering' in p['meta']:
            iwatering = ast.literal_eval(p['meta']['iwatering']).items()
            iwatering = sorted(iwatering, key=lambda elem: (s2d(elem[0])))[-3:]
            p['meta']['iwatering'] = {key: value for (key, value) in iwatering}
            p['meta']['iwatering'] = str(p['meta']['iwatering'])
        out += ' {}'.format(p['meta'])

        return out

       # ------------------------------------------------------------------------------------------------------------------
    # returns True if it is recommended to skip watering today
    def check_rain(self):

        self.weather.load()
        self.log('Weather: \n{}'.format(self.weather))
        # checking for the recent rain
        today = d2s(today_local())
        if today in self.weather():
            if self.weather()[today]['rain24'] > self.small_rain:  # small rain
                self.log("Will skip watering due to rain today {}mm".format(self.weather()[today]['rain24']), 'warn')
                return True

        yesterday = d2s(today_local() - datetime.timedelta(days=1))
        if yesterday in self.weather():
            if self.weather()[yesterday]['rain24'] > self.medium_rain:  # medium rain
                self.log("Will skip watering due to medium or heavy rain yesterday {}mm".format(self.weather()[yesterday]['rain24']), 'warn')
                return True
        twodaysago = d2s(today_local() - datetime.timedelta(days=2))
        if twodaysago in self.weather():
            if self.weather()[twodaysago]['rain24'] > self.big_rain:  # heavy rain
                self.log("Will skip watering due to heavy rain 2 days ago {}mm".format(self.weather()[twodaysago]['rain24']), 'warn')
                return True

        return False

    # ------------------------------------------------------------------------------------------------------------------
    def get_watering_days(self, plant):
        watering_days = {}
        if 'iwatering' not in plant['meta']:
            plant['meta']['iwatering'] = {}
        else:
            watering_days = ast.literal_eval(plant['meta']['iwatering'])
        return watering_days

    # ------------------------------------------------------------------------------------------------------------------
    def sort_plants(self, plants):
        totalDist = 0
        tr = sorted(plants, key=lambda elem: (int(elem['x']), int(elem['y'])))
        bl = sorted(plants, key=lambda elem: (int(elem['x']), int(-elem['y'])))
        dist, cur=min([ (self.distance(self.head,p), p) for p in (tr[0], tr[-1], bl[0], bl[-1])])
        path = [cur]
        for i in range(1,len(plants)):
            dists = [(self.distance(cur,p), p) for p in plants if p not in path]
            nextDist, cur = min(dists)
            totalDist += nextDist
            path.append(cur)

        return path

    # ------------------------------------------------------------------------------------------------------------------
    def run(self):

        #processing sequences
        try:
            for k in ('init','before','after','end'):
                if self.args[k]!=None:
                    self.args[k]=next(i for i in self.sequences() if i['name'].lower() == self.args[k].lower())
        except:
            raise ValueError('Sequence not found: {}'.format(self.args[k].upper()))

        #check if we need to enable iWatering
        iw = False
        if self.args['after'] != None and self.args['before'] == None:
            if all(x in self.args['after']['name'].lower() for x in ['mlh', 'water']):
                self.log("iWatering mode is engaged", 'warn')
                iw = True


        skip=self.check_rain() if iw else False
        #skip=False


        #processing points
        plants = [x for x in self.points() if self.is_eligible_point(x)]
        if len(plants) == 0:
            self.log('No plants selected by the filter, aborting','warn')
            return
        self.log('{} plants selected by the filter'.format(len(plants)), 'success')

        # execute init sequence
        self.execute_sequence(self.args['init'], 'INIT: ')

        processed=[]

        if iw:
            while True:
                distances=[(self.distance(x, self.head), x) for x in plants if x['name'] not in processed]
                if len(distances) == 0: break  # all done
                d,p=min(distances)
                to_process=self.sort_plants([x for x in plants if x['name'] == p['name']])
                self.process_plants(to_process, iw, skip)
                processed.append(p['name'])
        else:
            to_process = self.sort_plants(plants)
            self.process_plants(to_process, iw, skip)

        # execute end sequence
        self.execute_sequence(self.args['end'], "END: ")

    # ------------------------------------------------------------------------------------------------------------------
    def process_plants(self, plants, iw, skip):

        today_ls = d2s(today_local())
        travel_height = self.args['default_z']
        special=None

        if iw and not skip:
            try:
                special = next(i for i in self.sequences() if all(x in i['name'].lower() for x in ['mlh', 'water', plants[0]['name'].lower()]))
            except:
                special=None

            if special!=None:
                skip = True
                if today_ls not in self.get_watering_days(plants[0]):
                    self.log('All [{}] are handled by dedicated sequence {}'.format(plants[0]['name'], special['name']), 'warn')
                    self.execute_sequence(special)


        # iterate over all eligible plants
        for plant in plants:
            need_update=False
            message = 'Plant: ({:4d},{:4d}) {:15s} - {:s}'.format(plant['x'], plant['y'], plant['name'], self.finalize_log(plant))

            sq = self.args['after']
            if iw and not skip:
                if self.do_iwatering(sq, plant):
                    travel_height = self.get_travel_height(plant,self.args['default_z'])
                    need_update=True

            if not iw or need_update:
                self.execute_sequence(self.args['before'], 'BEFORE: ')
                if self.args['before']!=None or self.args['after']!=None:
                        if not skip:
                            location={'x': plant['x'], 'y': plant['y'], 'z': travel_height}
                            if self.head['z'] < travel_height:
                                self.move_absolute({'x': self.head['x'], 'y': self.head['y'], 'z': location['z']},message=None)
                            else:
                                self.move_absolute({'x': location['x'], 'y': location['y'], 'z': self.head['z']}, message=None)
                            self.move_absolute(location=location)

                if not skip: self.execute_sequence(sq, 'AFTER: ')

            if special!=None:
                watering_days=self.get_watering_days(plant)
                if today_ls not in watering_days:
                    watering_days[today_ls]=1
                    plant['meta']['iwatering'] = str(watering_days)
                    need_update = True
            if self.update_meta(plant):
                need_update=True

            if need_update:
                message += ' -> {}'.format(self.finalize_log(plant))
                self.put("points/{}".format(plant['id']), plant)

            self.log(message)
           


# ----------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":

    app = MLH()
    try:
        app.load_config()
        app.log(app.farmware_url)
        app.run()
        sys.exit(0)

    except requests.exceptions.HTTPError as error:
        app.log('HTTP error {} {} '.format(error.response.status_code,error.response.text[0:100]), 'error')
    except Exception as e:
        app.log('Something went wrong: {}'.format(str(e)), 'error')
    sys.exit(1)
