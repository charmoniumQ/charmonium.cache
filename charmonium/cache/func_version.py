import dis
import inspect
import types
from typing import Any, Callable

def closure_vars_version(closure_vars: inspect.ClosureVars) -> frozenset[tuple[str, Any]]:
    return {
        var: (func_version(val) if isinstance(val, types.FunctionType) else val)
        for var, val in {**closure_vars.nonlocals, **closure_vars.globals}.items()
    }

def func_version(func: Callable[..., Any]) -> tuple[Any]:
    return (
        # inspect.getsource is sensitive to comments, but dis.dis is not.
        list(dis.get_instructions(func)),
        closure_vars_version(inspect.getclosurevars(func))
    )
