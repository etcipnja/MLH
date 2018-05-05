# Problem:

When you have to deal with a lot of plants you might be puzzled that you have to create a dedicated sequence for each
instance of a plant. For exmaple: if you have 10 carrots - you probably need to create a watering sequence for every carrot
individually. (Disclaimer: I seriously hope that I am missing something and there is a standard solution for this
problem. But so far I don't know about any - so I wrote this farmware to help myself)

# Solution:

The idea is to write a loop that executes needed sequences for each eligible plant.
- Apply filters to select plants to be treated       		(Example: Select all Carrots with status "planned")
- Execute initial sequence                                  (Example: "Pick up seeder")
- For each plant:
    - Execute a sequence before moving to plant's location  (Example: "Grab a seed")
    - Move to plant's location
    - Execute a sequence at plant's location                (Example: "Plant a seed")
    - Update plant tags 	                                (Example: "Mark this instance of carrot as "planted")
- Execute end sequence                                      (Example: "Return seeder")

# Reference:

- FILTER BY PLANT NAME
    - Filter by plant names (comma separated) for example "Carrot, Beets", case insensitive, '*' means select all
- FILTER BY META DATA
    - MetaData is a piece of information (key:value) saved with the plant. Unfortunatelly you won't see it anywhere on
    the Farm Designer, but it is printed to the log. This farmware can update metadata, so you can use it in the
    filter later. See below about expected format and examples.
- INIT SEQUENCE NAME
    - Name of the sequence to be executed before anything (one time) or "None" to skip
- SEQUENCE NAME BEFORE NEXT MOVE
    - Sequence to be executed before the head moves to the plant (for every plant)
- SEQUENCE NAME AFTER MOVE
    - Sequence to be executed at plant's location (for every plant)
- END SEQUENCE NAME
    - Sequence to be executed at the end (one time)
- SAVE IN META DATA
    - Each plant will get its meta data updated upon successful completion of "AFTER" sequence. Please see below about
    expected format and examples
- DEFAULT Z AXIS VALUE WHEN MOVING
    - Z coordinate for the head while moving to the plant's location
- WHAT TO DO
    - "test" to skip actual movements and sequences (but still update meta data)
    - OR "real" - for the real action

Meta data fields require specially formatted input. In Python it is called "list of tupple pairs". Here is the example:

```
[ ( ‘key1’, ‘value1’ ) , ( ‘key2’, ‘value2’ ) ]
```

You can use whatever you want as a ‘key' and ‘value’ as long as they are strings.
More than one element in the list allows you to filter by multiple criteria and update multiple meta data tags at once!
Put "None" if you want to skip metadata feature.

There are special words with special meaning:
- key ‘plant_stage’ will not deal with metadata, instead it works with the attribute “Status” visible
in Farm Designer for every plant. Only valid values that go with this key are ‘planned’, ‘planted’ and ‘harvested’
- key ‘del’ in SAVE filed causes to delete currently saved meta data for this plant. If ‘value' is ‘*’ - all metadata is
deleted, otherwise only one key specified in ‘value’ is deleted
- value ‘today’ is replaced with actual today’s date. In FILTER you can write ‘!today’ which means “not today’.

# Examples:

Seed all "planned" Carrots and mark them "planted"
```
- FILTER BY PLANT NAME:             Carrot
- FILTER BY META DATA:              [('plant_stage','planned')]
- INIT SEQUENCE NAME:               Pickup seeder  (or whatever the name you have)
- SEQUENCE NAME BEFORE NEXT MOVE:   Pickup a seed
- SEQUENCE NAME AFTER MOVE:         Plant a seed
- END SEQUENCE NAME:                Return seeder
- SAVE IN META DATA:                [('plant_stage','planted')]
```

Please note that if you interrupt this sequence and restart it - it won't start seeding again from the beginning becasue
already seeded plants are marked as "planted" and won't be selected again.


Water all "planted" Carrots that have not been watered today
```
- FILTER BY PLANT NAME:             Carrot
- FILTER BY META DATA:              [('plant_stage','planted'), ('last_watering','!today')]
- INIT SEQUENCE NAME:               Pickup watering nozzle
- SEQUENCE NAME BEFORE NEXT MOVE:   None
- SEQUENCE NAME AFTER MOVE:         Water light
- END SEQUENCE NAME:                Return watering nozzle
- SAVE IN META DATA:                [('last_watering','today')]
```

Delete all meta data from all plants (does not affect plant_stage)
```
- FILTER BY PLANT NAME:             *
- FILTER BY META DATA:              None
- INIT SEQUENCE NAME:               None
- SEQUENCE NAME BEFORE NEXT MOVE:   None
- SEQUENCE NAME AFTER MOVE:         None
- END SEQUENCE NAME:                None
- SAVE IN META DATA:                [('del','*')]
```
Delete watering tag from all plants that were watered today
```
- FILTER BY PLANT NAME:             *
- FILTER BY META DATA:              [('last_watering','today')]
- INIT SEQUENCE NAME:               None
- SEQUENCE NAME BEFORE NEXT MOVE:   None
- SEQUENCE NAME AFTER MOVE:         None
- END SEQUENCE NAME:                None
- SAVE IN META DATA:                [('del','last_watering')]
```

# Installation:

Use this manifest to register farmware
https://raw.githubusercontent.com/etcipnja/MLH/master/MLH/manifest.json

# Bugs:

I noticed that if you change a parameter in WebApplication/Farmware form - you need to place focus on some other
field before you click "RUN". Otherwise old value is  passed to farmware script even though the new value
is displayed in the form.


# Credits:

The original idea belongs to @rdegosse with his Loop-Plants-With-Filters. https://github.com/rdegosse/Loop-Plants-With-Filters/blob/master/README.md
This Farmware - is a simplified version of it with nice perks about saving/filtering meta data

Thank you,
Eugene

