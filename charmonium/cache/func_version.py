import inspect
import types
from typing import Any, Callable


def closure_vars_version(closure_vars: inspect.ClosureVars,) -> Any:
    return {
        var: (func_version(val) if isinstance(val, types.FunctionType) else val)
        for var, val in {**closure_vars.nonlocals, **closure_vars.globals}.items()
    }


def func_version(func: Callable[..., Any]) -> Any:
    return (
        func.__code__.co_code,
        func.__code__.co_consts,
        closure_vars_version(inspect.getclosurevars(func)),
    )
