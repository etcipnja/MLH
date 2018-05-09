import os
import requests
import json

headers = {'Authorization': 'Bearer ' + os.environ['API_TOKEN'],
           'content-type': "application/json"}

sequence={
  "name": "Scare Birds",
  "body": [
    {
      "kind": "move_absolute",
      "args": {
        "location": {
          "kind": "coordinate",
          "args": {
            "x": 1,
            "y": 2,
            "z": 3
          }
        },
        "offset": {
          "kind": "coordinate",
          "args": {
            "x": 0,
            "y": 0,
            "z": 0
          }
        },
        "speed": 4
      }
    }
  ]
}

try:

    #create sequence
    response = requests.post('https://my.farmbot.io/api/sequences', headers=headers, data=json.dumps(sequence))
    response.raise_for_status()
    print(response.json()['body'])
    #update sequence name
    new_sequence=response.json()
    new_sequence['name']='may be2'
    response = requests.patch('https://my.farmbot.io/api/sequences/{}'.format(new_sequence['id']), headers=headers, data=json.dumps(new_sequence))
    response.raise_for_status()
    #body is gone!
    print(response.json()['body'])

except requests.exceptions.HTTPError as error:
    print('HTTP error {} {} '.format(error.response.status_code, error.response.text))