import os
import requests
import json

headers = {'Authorization': 'Bearer ' + os.environ['API_TOKEN'],
           'content-type': "application/json"}


def get_carrot():
    response = requests.get('https://my.farmbot.io/api/points', headers=headers)
    response.raise_for_status()
    points = response.json()
    carrot = next(x for x in points if x['name'] == 'Carrot')
    return carrot

try:

    carrot=get_carrot()
    print(carrot['id'],carrot['meta'])  #non-empty meta
    carrot['meta']={}                   #drop meta and save
    response = requests.put('https://my.farmbot.io/api/points/{}'.format(carrot['id']), headers=headers, data=json.dumps(carrot))
    response.raise_for_status()
    print(response.json()['meta'])      #confirm that it is dropped

    carrot = get_carrot()
    print(carrot['id'], carrot['meta'])  # or is it!?

except requests.exceptions.HTTPError as error:
    print('HTTP error {} {} '.format(error.response.status_code, error.response.text))