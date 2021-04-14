from pathlib import Path
import json
import subprocess
import sys
import textwrap
from typing import TypedDict, cast

import cloudpickle as cp  # type: ignore
import dill  # type: ignore


ScriptResult = TypedDict(
    "ScriptResult", {"foo_loaded": dict[str, int], "foo_serialized": dict[str, bytes]}
)


def run_script(foo_val: int, write_to_disk: bool, as_main: bool) -> ScriptResult:
    directory = Path("/tmp/test_picklers")
    directory.mkdir(exist_ok=True)
    script = directory / "script.py"
    write_to_disk_str = (
        """
for serializer in serializers:
    (directory / serializer.__name__).write_bytes(foo_serialized[serializer.__name__])
"""
        if write_to_disk
        else ""
    )

    script.write_text(
        f"""
from pathlib import Path
import json
import base64

import cloudpickle
import dill

directory = Path("{directory!s}")

serializers = [cloudpickle, dill]

def foo():
    return {foo_val}
def bar():
    return foo()

foo_serialized = {{
    serializer.__name__: serializer.dumps(foo)
    for serializer in serializers
}}
{write_to_disk_str}
foo_loaded = {{
    serializer.__name__: serializer.loads((directory / serializer.__name__).read_bytes())()
    for serializer in serializers
}}
print(json.dumps({{
    "foo_loaded": foo_loaded,
    "foo_serialized": {{
        serializer: base64.b64encode(bytez).decode()
        for serializer, bytez in foo_serialized.items()
    }},
}}))
""".lstrip()
    )
    cmd = ["script.py"] if as_main else ["-m", "script"]
    proc = subprocess.run([sys.executable, *cmd], cwd=directory, capture_output=True, text=True)
    if proc.stderr:
        print(
            f"""
script:
{textwrap.indent(script.read_text(), "    ")}
stderr:
{textwrap.indent(proc.stderr, "    ")}
""".lstrip()
        )
        raise ValueError("Script failed")
    return cast(ScriptResult, json.loads(proc.stdout))


def test_picklers() -> None:
    for as_main in [False, True]:
        result = run_script(foo_val=3, write_to_disk=True, as_main=as_main)
        assert set(result["foo_loaded"].values()) == {3}, "Test script messed up"
        last_result = result

        result = run_script(foo_val=3, write_to_disk=True, as_main=as_main)
        assert as_main == (
            last_result["foo_serialized"]["cloudpickle"] == result["foo_serialized"]["cloudpickle"]
        ), "cloudpickle should have the same hash between runs with identical source, iff as_main == True"
        assert (
            last_result["foo_serialized"]["dill"] == result["foo_serialized"]["dill"]
        ), "dill should have the same hash between runs with identical source"

        result = run_script(foo_val=4, write_to_disk=False, as_main=as_main)
        for serializer, value in result["foo_loaded"].items():
            assert value == 3, f"{serializer} should use serialized closed-over variables"  # type


if __name__ == "__main__":
    test_picklers()
