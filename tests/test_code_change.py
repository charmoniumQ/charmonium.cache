from __future__ import annotations

import itertools
import json
import subprocess
import sys
import tempfile
import textwrap
import time
from typing import TYPE_CHECKING, Any, cast

import pytest

from charmonium.cache.pathlike import PathLikeFrom, pathlike_from

if TYPE_CHECKING:
    from typing import TypedDict

else:
    TypedDict = lambda a, b: b


if TYPE_CHECKING:
    ScriptResult = TypedDict(
        "ScriptResult",
        {
            "returns": list[int],
            "recomputed": list[int],
            "serialized": dict[str, bytes],
            "expected": list[int],
        },
    )
else:
    ScriptResult = Any


def run_script(
    directory: PathLikeFrom,
    name: str = "",
    source_var: int = 1,
    closure_var: int = 2,
    closure_func_source_var: int = 3,
    other_var: int = 4,
    as_main: bool = False,
    inputs: list[int] = [2, 3, 2],
) -> ScriptResult:
    script = pathlike_from(directory) / f"script_{name}.py"
    script.parent.mkdir(exist_ok=True)

    script.write_text(
        f"""
import base64
import json
from charmonium.cache import memoize, hashable, determ_hash

def closure_func():
    return {closure_func_source_var}

closure_var = {closure_var}

@memoize(lossy_compression=False)
def func(input):
    return (input**{source_var} + closure_func()) * closure_var

returns = []
for input in {json.dumps(inputs)}:
    returns.append(func(input))

# import cloudpickle
# import dill
import pickle

serializers = dict(
    # dill=dill.dumps,
    # cloudpickle=cloudpickle.dumps,
    func_version=lambda fn: pickle.dumps(determ_hash(hashable(fn))),
)

print(json.dumps(dict(
    recomputed=[dict(x)[0] for (_, _, _, x, _), _ in func.group._index.items()],
    returns=returns,
    serialized={{
        serializer_name: base64.b64encode(serializer(func._func)).decode()
        for serializer_name, serializer in serializers.items()
    }},
)))
""".lstrip()
    )
    cmd = [script.name] if as_main else ["-m", script.stem]
    proc = subprocess.run(
        [sys.executable, *cmd], cwd=script.parent, capture_output=True, text=True
    )
    if proc.returncode != 0:
        print(
            f"""
script:
{textwrap.indent(script.read_text(), "    ")}
stdout:
{textwrap.indent(proc.stdout, "    ")}
stderr:
{textwrap.indent(proc.stderr, "    ")}
""".lstrip()
        )
        raise ValueError("Script failed")
    out_str = proc.stdout.strip().split("\n")
    return cast(
        ScriptResult,
        {
            "expected": [
                (input ** source_var + closure_func_source_var) * closure_var
                for input in inputs
            ],
            **json.loads(out_str[-1]),
        },
    )


vars_ = {
    "source_var": 1,
    "other_var": 2,
    "closure_var": 3,
    "closure_func_source_var": 4,
}


@pytest.mark.parametrize(
    "serializer,change,as_main",
    itertools.product(["func_version"], vars_.keys(), [False],),
)
def test_code_change(serializer: str, change: str, as_main: bool) -> None:
    with tempfile.TemporaryDirectory() as directory:

        result = run_script(directory=directory, as_main=as_main, **vars_)
        assert result["expected"] == result["returns"]

        # CPython use __pycache__ to cache the Python byte code for a given script
        # It detects invalidations using modtime.
        # Without this sleep, the modtimes are too close for CPython to detect invalidation.
        time.sleep(0.01)

        result2 = run_script(
            directory=directory, as_main=as_main, **{**vars_, change: 10}
        )
        assert result2["expected"] == result2["returns"]

        if change in {"other_var"}:
            assert result["serialized"][serializer] == result2["serialized"][serializer]
        elif change in {"closure_var", "closure_func_source_var", "source_var"}:
            assert result["serialized"][serializer] != result2["serialized"][serializer]
        else:
            raise ValueError(
                f"Unknown change type {change}. Should be one of {list(vars_)}"
            )
