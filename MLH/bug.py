import os
import requests
import json

headers = {'Authorization': 'Bearer ' + os.environ['API_TOKEN'],
           'content-type': "application/json"}


def get_carrot():
    response = requests.get('https://my.farmbot.io/api/points', headers=headers)
    response.raise_for_status()
    points = response.json()
    carrot = next(x for x in points if x['name'] == 'Cannabis')
    return carrot

try:

    carrot=get_carrot()
    carrot['x']=-100
    carrot['y'] = -100
    carrot['name'] = 'Side Garden'
    response = requests.put('https://my.farmbot.io/api/points/{}'.format(carrot['id']), headers=headers, data=json.dumps(carrot))
    response.raise_for_status()
    print(response.json())


except requests.exceptions.HTTPError as error:
    print('HTTP error {} {} '.format(error.response.status_code, error.response.text))