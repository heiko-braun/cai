import json

def show_json(obj):
    json_object = json.loads(obj.model_dump_json())
    pretty_json = json.dumps(json_object, indent=2)
    print(pretty_json)

def as_json(obj):
    json_object = json.loads(obj.model_dump_json())
    return json_object
    