from __future__ import annotations

import builtins
import copy
import dis
import inspect
import pickle
import struct
from pathlib import Path
from types import (
    BuiltinFunctionType,
    BuiltinMethodType,
    ClassMethodDescriptorType,
    CodeType,
    FunctionType,
    GetSetDescriptorType,
    MemberDescriptorType,
    MethodDescriptorType,
    MethodType,
    MethodWrapperType,
    ModuleType,
    WrapperDescriptorType,
)
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    FrozenSet,
    Hashable,
    List,
    Mapping,
    Set,
    Tuple,
    Type,
    cast,
)

import xxhash

from .util import GetAttr

if TYPE_CHECKING:
    from typing import Protocol

else:
    Protocol = object


HASH_BITS = 32
HASH_BYTES = HASH_BITS // 8 + int(bool(HASH_BITS % 8))


class Hasher(Protocol):
    def __init__(self, initial_value: bytes = ...) -> None:
        # pylint: disable=super-init-not-called
        ...

    def update(self, value: bytes) -> None:
        ...

    def intdigest(self) -> int:
        ...


# pylint: disable=invalid-name
def determ_hash(obj: Hashable, HasherType: Type[Hasher] = xxhash.xxh64) -> int:
    """A deterministic hash protocol.

    Python's |hash|_ will return different values across different
    processes. This hash is deterministic across:

    - different processes
    - different machines
    - different Python versions
    - different OSes

    ``determ_hash`` is based on the contents:

    - Primitive types (bytes, str, int, float, complex, None) are
      hashed by their value or a checksum of their value.

    - Immutable container types (tuple, frozenset) are hashed by the
      XOR of their elements.

    - Objects containing a ``__determ_hash__`` hashed by calling
      determ_hash on its return (it need not be an int).

.. |hash| replace:: ``hash``
.. _`hash`: https://docs.python.org/3/library/functions.html?highlight=hash#hash

    """
    hasher = HasherType()
    _determ_hash(obj, hasher)
    return hasher.intdigest()


def _determ_hash(obj: Any, hasher: Hasher) -> None:
    # Naively, hash of empty output might map to 0.
    # But empty is a popular input.
    # If any two branches have 0 as a popular output, collisions ensue.
    # Therefore, I try to make each branch section have a different ouptut for empty/zero/nil inputs.
    # I do this by seeding each with the name of their type, hash("tuple") ^ hash(elem0) ^ hash(elem1) ^ ...
    # This way, the empty tuple and empty frozenset map to different outputs.
    if isinstance(obj, type(None)):
        hasher.update(b"none")
    elif isinstance(obj, bytes):
        hasher.update(b"bytes")
        hasher.update(obj)
    elif isinstance(obj, str):
        hasher.update(b"str")
        hasher.update(obj.encode())
    elif isinstance(obj, int):
        hasher.update(b"int")
        hasher.update(
            obj.to_bytes(
                length=(8 + (obj + (obj < 0)).bit_length()) // 8,
                byteorder="big",
                signed=True,
            )
        )
    elif isinstance(obj, float):
        hasher.update(b"float")
        hasher.update(struct.pack("!d", obj))
    elif isinstance(obj, complex):
        hasher.update(b"complex")
        _determ_hash(obj.imag, hasher)
        _determ_hash(obj.real, hasher)
    elif isinstance(obj, type(...)):
        hasher.update(b"...")
    elif isinstance(obj, tuple):
        hasher.update(b"tuple(")
        for elem in cast(Tuple[Hashable], obj):
            _determ_hash(elem, hasher)
        hasher.update(b")")
    elif isinstance(obj, frozenset):
        hasher.update(b"frozenset(")
        for elem in cast(FrozenSet[Any], obj):
            _determ_hash(elem, hasher)
        hasher.update(b")")
    elif isinstance(obj, BuiltinFunctionType):
        hasher.update(b"builtinfunctiontype")
        hasher.update(obj.__qualname__.encode())
    elif hasattr(obj, "__determ_hash__") and hasattr(
        getattr(obj, "__determ_hash__"), "__self__"
    ):
        proxy = getattr(obj, "__determ_hash__")()
        hasher.update(b"__determ_hash__")
        _determ_hash(proxy, hasher)
    else:
        raise TypeError(f"{obj} ({type(obj)}) is not determ_hashable")


def hashable(
    obj: Any,
    verbose: bool = False
    # DO NOT COMMIT: chnage verbose to False
) -> Hashable:
    """An injective function that maps anything to a hashable object.

    When given a mutable type, hashable makes an immutable copy of the
    current state.

    The output of this function is also human-readable. It won't
    totally obfuscate debugging.

    Special cases:

    - Objects with ``__determ_hash__`` are hashed by making whatever
      that returns hashable.

    - Functions are hashed by their bytecode, constants, and
      closure-vars. This means changing comments will not change the
      hashable value.

    This function can learn how to handle other types through
    :py:func:`~charmonium.cache.register_hashable`.

    """
    if verbose:
        print(f"_hashable({obj}, set(), 0) =")
    ret = _hashable(obj, set(), 0, verbose)
    return ret


attr_blacklist = {
    "__doc__",
    "__weakref__",
    "__dict__",  # the actual attributes will get saved
}


def _hashable(obj: Any, tabu: set[int], level: int, verbose: bool) -> Hashable:
    # pylint: disable=too-many-branches,too-many-return-statements
    # Make sure I remember to pass tabu and level
    # Make sure I update tabu when I call _determ_hash on a mutable object.
    # I prepend the type if it is a container so that an empty tuple and empty list hash to different keys.

    if level > 50:
        raise ValueError("Maximum recursion")

    if verbose:
        print(level * " ", repr(obj), type(obj))

    if isinstance(
        obj,
        (type(None), bytes, str, int, float, complex, BuiltinFunctionType, type(...)),
    ):
        return obj
    elif id(obj) in tabu:
        return b"cycle detected"
    elif isinstance(obj, bytearray):
        return bytes(obj)
    elif isinstance(obj, (tuple, list)):
        tabu = tabu | {id(cast(Any, obj))}
        level = level + 1
        return tuple(
            _hashable(elem, tabu, level, verbose) for elem in cast(List[Any], obj)
        )
    elif isinstance(obj, (set, frozenset)):
        tabu = tabu | {id(cast(Any, obj))}
        level = level + 1
        return frozenset(
            _hashable(elem, tabu, level, verbose) for elem in cast(Set[Any], obj)
        )
    elif isinstance(obj, dict):
        tabu = tabu | {id(cast(Any, obj))}
        level = level + 1
        return frozenset(
            (key, _hashable(val, tabu, level, verbose))
            for key, val in cast(Dict[Any, Any], obj).items()
        )
    elif hasattr(obj, "__determ_hash__") and hasattr(
        getattr(obj, "__determ_hash__"), "__self__"
    ):
        tabu = tabu | {id(cast(Any, obj))}
        level = level + 1
        proxy = getattr(obj, "__determ_hash__")()
        return _hashable(proxy, tabu, level, verbose)
    elif hasattr(obj, "data") and isinstance(getattr(obj, "data"), memoryview):
        # Fast path for numpy arrays
        data = GetAttr[memoryview]()(obj, "data")
        return data.tobytes()
    elif isinstance(
        obj,
        (
            BuiltinMethodType,
            MethodWrapperType,
            WrapperDescriptorType,
            MethodDescriptorType,
            MemberDescriptorType,
            ClassMethodDescriptorType,
            GetSetDescriptorType,
        ),
    ):
        tabu = tabu | {id(cast(Any, obj))}
        level = level + 1
        return (
            obj.__qualname__,
            _hashable(getattr(obj, "__self__", None), tabu, level, verbose),
        )
    elif isinstance(obj, FunctionType):
        tabu = tabu | {id(obj)}
        level = level + 1
        closure = getclosurevars(obj)
        return (
            _hashable(obj.__code__, tabu, level, verbose),
            _hashable(closure.nonlocals, tabu, level, verbose),
            _hashable(closure.globals, tabu, level, verbose),
        )
    elif isinstance(obj, CodeType):
        return (
            obj.co_name,  # name of function
            obj.co_varnames,  # argument names and local var names
            obj.co_consts,  # constants used by code
            obj.co_code,  # source code of function
        )
    elif isinstance(obj, MethodType):
        tabu = tabu | {id(obj)}
        level = level + 1
        return (
            obj.__qualname__,
            _hashable(obj.__self__, tabu, level, verbose),
            _hashable(obj.__class__, tabu, level, verbose),
        )
    elif isinstance(obj, property):
        tabu = tabu | {id(obj)}
        level = level + 1
        return (
            _hashable(obj.fget, tabu, level, verbose),
            _hashable(obj.fset, tabu, level, verbose),
            _hashable(obj.fdel, tabu, level, verbose),
        )
    elif isinstance(obj, ModuleType):
        tabu = tabu | {id(obj)}
        level = level + 1
        return obj.__name__
    elif isinstance(obj, Path):
        return obj.__fspath__()
    else:
        tabu = tabu | {id(obj)}
        level = level + 1
        for pred, hashable_fn in HASHABLE_FNS:
            if pred(obj):
                return hashable_fn(obj, tabu, level, verbose)
        slots = getattr(type(obj), "__slots__", None)
        print("slots", obj, type(obj), slots)
        dct = getattr(obj, "__dict__", None)
        ignore_attrs = {"__module__", "__dict__", "__weakref__", "__doc__"}
        if slots is not None:
            slots_val = {attr: getattr(obj, attr) for attr in slots}
            print("slots", slots_val)
            return frozenset(
                (attr, _hashable(getattr(obj, attr), tabu, level, verbose))
                for attr, val in slots_val.items()
                if attr not in ignore_attrs and val is not getattr(object, attr, None)
            )
        elif dct is not None:
            return frozenset(
                (attr, _hashable(val, tabu, level, verbose))
                for attr, val in dct.items()
                if attr not in ignore_attrs and val is not getattr(object, attr, None)
            )
        else:
            raise TypeError(f"{type(obj)} {obj} is not able to be made hashable")


HASHABLE_FNS: list[
    tuple[Callable[[Any], bool], Callable[[Any, set[int], int, bool], Hashable]]
] = []


def register_hashable(
    pred: Callable[[Any], bool],
    hashable_fn: Callable[[Any, set[int], int, bool], Hashable],
) -> None:
    """Teach :py:func:`~charmonium.cache.hashable` another type.

    If none of defualt hashable handlers apply, then ``hashable``
    begins searching this table. If ``pred`` returns true, then this
    entry applies, and ``hashable_fn`` should return a hashable proxy
    of its input.

    Note that this object should be the same for differente OSes,
    platforms, and Python versions. Hashes being equal should usually
    mean the objects are equal.

    """
    HASHABLE_FNS.append((pred, hashable_fn))


def pickle_fallback(obj: Any, _tabu: set[int], _level: int, _verbose: bool) -> Any:
    if not isinstance(obj, (ModuleType, FunctionType)) and copy.deepcopy(obj) != obj:
        raise TypeError(
            "This type isn't equal to its deepcopy; it can't be made hashable"
        )
    try:
        return pickle.dumps(obj, protocol=4)
    except (pickle.PickleError, AttributeError, TypeError, ImportError) as exc:
        raise TypeError("{type(obj)} is not able to be made into a hashable") from exc


def attr_fallback(obj: Any, tabu: set[int], level: int, verbose: bool) -> Any:
    tabu = tabu | {id(obj)}
    level = level + 1
    return frozenset(
        (
            (attr_name, _hashable(getattr(obj, attr_name), tabu, level, verbose),)
            for attr_name in dir(obj)
            if (
                attr_name not in attr_blacklist
                and
                # double check we actually have this attr
                hasattr(obj, attr_name)
                and not attr_name.startswith("__")
                and
                # make sure this isn't inherited
                id(getattr(obj, attr_name, 1)) != id(getattr(type(obj), attr_name, 2))
            )
        )
    )


def getclosurevars(func: FunctionType) -> Mapping[str, Any]:
    """A clone of inspect.getclosurevars that is robust to [this bug][1]

[1]: https://stackoverflow.com/a/61964607/1078199
"""
    nonlocal_vars = {
        var: cell.cell_contents
        for var, cell in zip(func.__code__.co_freevars, func.__closure__ or [])
    }

    global_names = set()
    local_varnames = set(func.__code__.co_varnames)
    for instruction in dis.get_instructions(func):
        if instruction.opname in {
            "LOAD_GLOBAL",
            "STORE_GLOBAL",
            "LOAD_DEREF",
            "STORE_DEREF",
        }:
            name = instruction.argval
            if name not in local_varnames:
                global_names.add(name)

    # Global and builtin references are named in co_names and resolved
    # by looking them up in __globals__ or __builtins__
    global_ns = func.__globals__
    builtin_ns = global_ns.get("__builtins__", builtins.__dict__)
    if inspect.ismodule(builtin_ns):
        builtin_ns = builtin_ns.__dict__
    global_vars = {}
    builtin_vars = {}
    unbound_names = set()
    for name in global_names:
        if name in ("None", "True", "False"):
            # Because these used to be builtins instead of keywords, they
            # may still show up as name references. We ignore them.
            continue
        try:
            global_vars[name] = global_ns[name]
        except KeyError:
            try:
                builtin_vars[name] = builtin_ns[name]
            except KeyError:
                unbound_names.add(name)

    return inspect.ClosureVars(nonlocal_vars, global_vars, builtin_vars, unbound_names,)
