import inspect
import types
from typing import Any, Callable


def closure_vars_version(closure_vars: inspect.ClosureVars,) -> Any:
    return {
        var: (func_version(val) if isinstance(val, types.FunctionType) else val)
        for var, val in {**closure_vars.nonlocals, **closure_vars.globals}.items()
    }


def func_version(func: Callable[..., Any]) -> Any:
    """func_version is injective (different when the input is different).

    The func_version depends on the functions source-code and its
    `closure`_. If the closure contains a function, that function is
    recorded by func_version as well.

    .. _`closure`: https://en.wikipedia.org/wiki/Closure_(computer_programming)

    """
    return (
        func.__code__.co_code,
        func.__code__.co_consts,
        closure_vars_version(inspect.getclosurevars(func)),
    )
