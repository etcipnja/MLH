import os
import ast
import datetime
import sys
from Farmware import Farmware

class MLH(Farmware):
    def __init__(self):
        Farmware.__init__(self,((__file__.split(os.sep))[len(__file__.split(os.sep)) - 3]).replace('-master', ''))

    # ------------------------------------------------------------------------------------------------------------------
    def load_config(self):
        prefix = self.app_name.lower().replace('-', '_')
        self.params = {}

        self.params['pointname'] = os.environ.get(prefix + "_pointname", '*').lower().split(',')
        self.params['sequence'] = {'init': {'name': os.environ.get(prefix + '_init', 'None'), 'id': -1},
                                   'before': {'name': os.environ.get(prefix + '_before', 'None'), 'id': -1},
                                   'after': {'name': os.environ.get(prefix + '_after', 'None'), 'id': -1},
                                   'end': {'name': os.environ.get(prefix + '_end', 'None'), 'id': -1}}
        self.params['default_z'] = int(os.environ.get(prefix + "_default_z", -300))
        self.params['action'] = os.environ.get(prefix + "_action", 'test')
        filter = os.environ.get(prefix + "_filter_meta", "None")
        save = os.environ.get(prefix + "_save_meta", "None")

        try:
            self.params['filter_meta'] = ast.literal_eval(filter)
            self.params['save_meta'] = ast.literal_eval(save)  # \"date\",\"today\"

            if not isinstance(self.params['filter_meta'], list) and self.params['filter_meta']!=None:
                raise ValueError
            if not isinstance(self.params['save_meta'], list) and self.params['save_meta']!=None:
                raise ValueError
        except:
            raise ValueError("Invalid meta {} or {}".format(filter, save))



        self.log(str(self.params))

    # ------------------------------------------------------------------------------------------------------------------
    def is_eligible(self, p):

        if p['pointer_type'].lower() != 'plant': return False
        if p['name'].lower() not in self.params['pointname'] and '*' not in self.params['pointname']: return False

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

            return need_update

    # ------------------------------------------------------------------------------------------------------------------
    def run(self):

        if self.params['action'] == "test":
            self.log("TEST MODE, no sequences or movement will be run, meta information will be updated",'warn')
            debug=True
        else:
            debug=False

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
        if len(mypoints)==0:
            self.log('No plants selected by the filter, aborting', 'error')
        else:
            self.log('{} plants selected by the filter'.format(len(mypoints)),'success')

            # sort points for optimal movement
            mypoints = sorted(mypoints, key=lambda elem: (int(elem['x']), int(elem['y'])))

            # execute init sequence
            self.execute_sequence(self.params['sequence']['init'], debug, 'INIT: ')

            # iterate over all eligible points
            for point in mypoints:
                message='Plant: ({:4d},{:4d}) {:s} - {:s} {}'.format(point['x'], point['y'], point['name'],point['plant_stage'], point['meta'])
                self.execute_sequence(self.params['sequence']['before'], debug, 'BEFORE: ')
                if self.params['sequence']['before']['id']!=-1 or self.params['sequence']['after']['id']!=-1:
                    self.move_absolute({'x': point['x'], 'y': point['y'], 'z': self.params['default_z']},{'x': 0, 'y': 0, 'z': 0}, debug)
                self.execute_sequence(self.params['sequence']['after'], debug, 'AFTER: ')
                if self.save_meta(point):
                    message+=' -> {}'.format(point['meta'])
                self.log(message)

            # execute end sequence
            self.execute_sequence(self.params['sequence']['end'], debug, "END: ")


# ----------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":

    try:
        app = MLH()
        app.load_config()
        app.run()
        sys.exit(0)

    except Exception as e:
        app.log('Something went wrong: {}'.format(str(e)), 'error')
    sys.exit(1)
