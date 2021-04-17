
import base64, dis, inspect, json

def func(input):
    return 2

print(json.dumps(dict(
    source=inspect.getsource(func),
    instructions="\n".join(map(repr, dis.get_instructions(func))),
    bytecode=base64.b64encode(func.__code__.co_code).decode(),
)))
