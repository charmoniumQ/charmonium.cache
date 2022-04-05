from __future__ import annotations

import itertools
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Dict, List, TypedDict, cast

import pytest

ScriptResult = TypedDict(
    "ScriptResult",
    {
        "returns": List[int],
        "recomputed": List[int],
        "serialized": Dict[str, bytes],
        "expected": List[int],
    },
)


def run_script(
    directory: Path,
    name: str = "",
    source_var: int = 1,
    closure_var: int = 2,
    closure_func_source_var: int = 3,
    other_var: int = 4,
    as_main: bool = False,
    inputs: list[int] = [2, 3, 2],
) -> ScriptResult:
    script = directory / f"script_{name}.py"
    script.parent.mkdir(exist_ok=True)

    script.write_text(
        f"""
import base64
import json
from charmonium.cache import memoize
from charmonium.freeze import freeze
from charmonium.determ_hash import determ_hash

def closure_func():
    return {closure_func_source_var}

closure_var = {closure_var}

@memoize(lossy_compression=False)
def func(input):
    return (input**{source_var} + closure_func()) * closure_var

returns = []
for input in {json.dumps(inputs)}:
    returns.append(func(input))

other_var = {other_var}

# import cloudpickle
# import dill
import pickle

serializers = dict(
    # dill=dill.dumps,
    # cloudpickle=cloudpickle.dumps,
    func_version=lambda fn: pickle.dumps(determ_hash(freeze(fn))),
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
                (input**source_var + closure_func_source_var) * closure_var
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
    itertools.product(
        ["func_version"],
        vars_.keys(),
        [False],
    ),
)
def test_code_change(serializer: str, change: str, as_main: bool) -> None:
    with tempfile.TemporaryDirectory() as directory_:
        directory = Path(directory_)
        pycache = directory / "__pycache__"

        result = run_script(directory=directory, as_main=as_main, **vars_)
        assert result["expected"] == result["returns"]

        # CPython use __pycache__ to cache the Python byte code for a given script
        if pycache.exists():
            shutil.rmtree(pycache)

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
