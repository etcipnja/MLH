# Problem:

When you have to deal with a lot of plants you might be puzzled that you have to create a dedicated sequence for each
instance of a plant. For example: if you have 10 carrots - you probably need to create a watering sequence for every carrot
individually.

# Solution:

The idea is to write a loop that executes needed sequences for each eligible plant.
- Apply filters to select plants to be treated       		(Example: Select all Carrots with status "planned")
- Execute initial sequence                                  (Example: "Pick up seeder")
- For each plant:
    - Execute a sequence before moving to plant's location  (Example: "Grab a seed")
    - Move to plant's location
    - Execute a sequence at plant's location                (Example: "Plant a seed")
    - Update plant meta 	                                (Example: "Mark this instance of carrot as "planted")
- Execute end sequence                                      (Example: "Return seeder")

# Reference:

- FILTER BY PLANT NAME
    - Filter by plant names (comma separated) for example "Carrot, Beets", case insensitive, '*' means select all
    - You can negate search by providing '!' as the first element. For example "!, Carrot, Beets" selects all but
    Carrots and Beets
- FILTER BY META DATA
    - Meta is a piece of information (key:value) saved with the plant. Unfortunately, you won't see it anywhere in
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
    - Each plant will get it's meta data updated upon successful completion of "AFTER" sequence. Please see below about
    expected format and examples
- DEFAULT Z AXIS VALUE WHEN MOVING
    - Z coordinate for the head while moving to the plant's location
- WHAT TO DO
    - "test" to skip actual movements, sequences and don't update meta
    - OR "real" - for the real action

Meta data fields require specially formatted input. In Python it is called "list of tupple pairs". Here is the example:

```
[ ( ‘key1’, ‘value1’ ) , ( ‘key2’, ‘value2’ ) ]
```

You can use whatever you want as a ‘key' and ‘value’ as long as they are strings.
More than one element in the list allows you to filter by multiple criteria and update multiple meta data at once!
Put "None" if you want to skip metadata feature.

There are special keys and values with special meaning:
- key ‘plant_stage’ will not deal with metadata, instead it works with the attribute “Status” visible
in Farm Designer for every plant. Only valid values that go with this key are ‘planned’, ‘planted’ and ‘harvested’
- key 'planted_at' - also not stored in meta - this is the date when plant was planted. It's value shall be in the format
YYYY-MM-DD (Example: "2018-04-15")
- key ‘del’ in SAVE filed causes to delete existing meta data for this plant. If ‘value' is ‘*’ - all metadata is
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

Please note that if you interrupt this sequence and restart it - it won't start seeding again from the beginning because
already seeded plants are marked as "planted" and won't be selected again in the next run.


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

Sets up the date when the plants were planted
```
- FILTER BY PLANT NAME:             Carrots
- FILTER BY META DATA:              [('plant_stage','planted')
- INIT SEQUENCE NAME:               None
- SEQUENCE NAME BEFORE NEXT MOVE:   None
- SEQUENCE NAME AFTER MOVE:         None
- END SEQUENCE NAME:                None
- SAVE IN META DATA:                [('planted_at','2018-04-01')    #YYYY-MM-DD
```


# Intelligent watering (iWatering):

Intelligent watering tries to solve a problem that watering shall depend of:
- plant size
- plant age
- weather condition

To engage iWatering mode you need to provide AFTER sequence name that has 'water' and 'mlh' in it (For example:
"Water [MLH]"). This sequence shall be doing the following
- opening watering valve
- waiting 1 sec
- closing watering valve

It can also do whatever you want, the only important part is "waiting"
The idea is that Farmware will update the "waiting" duration basing on its understanding of how much water this
particular plant needs. Note: My assumptions about this may be different from yours - if you are not happy with it -
fork my project and help yourself.

Weather reading is taken from my other farmware "Netatmo". Please note that MLH doesn't call Netatmo explicitly. I
recommend to create a sequence like "Water All" and call Netatmo and MLH from there one after another.

iWatering skips the watering today if:
- plant was already watered today
- there was a rain today >1mm
- there was a rain yesterday >10mm
- there was a rain 2 days ago >20mm

IMPORTANT: The amount of watering is calculated basing on plant's age - make sure your planted_at date is set correctly.
See above for example.

Algorithm to calculate the amount of watering:
- get plant spread from openfarm
- adjust spread to plant's age
- convert spread (mm) into volume (ml) using my best guess
- convert ml into ms assuming that water nozzle produces 80ml every 1000ms
- update the delay in watering sequence

If you want to provide custom sequence for watering of your particular plant name - call it so it has 'water', 'mlh' and
<your_plant_name> in its name. In this case this sequence will be called once for all plants of this name and no
built-in watering will be performed. For example if farmware finds "Water [MLH] - Carrot" - this sequence will be called
when all carrots have to be watered and "Water [MLH]" will NOT be called.

# Installation:

Use this manifest to register farmware
https://raw.githubusercontent.com/etcipnja/MLH/master/MLH/manifest.json

# Bugs:

I noticed that if you change a parameter in WebApplication/Farmware form - you need to place focus on some other
field before you click "RUN". Otherwise old value is  passed to farmware script even though the new value
is displayed in the form.

In Intelligent Watering mode I need to update  watering sequence and sync it from within the farmware.
Sync function doesn't work stable sometimes. As the result the correct duration is not pushed to the bot and watering
will be wrong. This is pretty important problem as it may ruin your plants with excessive watering. I plan to submit
ticket to support as it is a problem of the platform, not the farmware.

# Credits:

The original idea belongs to @rdegosse with his Loop-Plants-With-Filters. https://github.com/rdegosse/Loop-Plants-With-Filters/blob/master/README.md

Thank you,
Eugene

