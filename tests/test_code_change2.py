import json, subprocess, sys, pathlib, time

def run_script(source):
    script = pathlib.Path("script2.py")

    script.write_text(
        f"""
import base64, dis, inspect, json

def func(input):
    return {source}

print(json.dumps(dict(
    source=inspect.getsource(func),
    instructions="\\n".join(map(repr, dis.get_instructions(func))),
    bytecode=base64.b64encode(func.__code__.co_code).decode(),
)))
""")
    proc = subprocess.run([sys.executable, "-m", script.stem], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)

result1 = run_script(1)
result2 = run_script(2)
print("Source is diff:", result1["source"] != result2["source"])
print("dis.get_instructions are same:", result1["instructions"] == result2["instructions"])
print("bytecode is same:", result1["bytecode"] == result2["bytecode"])
print()
print(result1["source"].strip())
print(result1["instructions"])
print()
print(result2["source"].strip())
print(result2["instructions"])
