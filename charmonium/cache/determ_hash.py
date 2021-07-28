from __future__ import annotations

import copy
import functools
import inspect
import operator
import pickle
import struct
import sys
import zlib
from pathlib import Path
from types import BuiltinFunctionType, BuiltinMethodType, FunctionType, MethodType, ModuleType
from typing import Any, Callable, Dict, FrozenSet, Hashable, List, Set, Tuple, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import Protocol

else:
    Protocol = object

import xxhash

from .util import GetAttr

HASH_BITS = 32
HASH_BYTES = HASH_BITS // 8 + int(bool(HASH_BITS % 8))


class Hasher(Protocol):
    def __init__(self, initial_value: bytes) -> None: ...
    def update(self, value: bytes) -> None: ...
    def intdigest(self) -> int: ...


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
    # Naively, hash of empty output might map to 0.
    # But empty is a popular input.
    # If any two branches have 0 as a popular output, collisions ensue.
    # Therefore, I try to make each branch section have a different ouptut for empty/zero/nil inputs.
    # I do this by seeding each with the name of their type, hash("tuple") ^ hash(elem0) ^ hash(elem1) ^ ...
    # This way, the empty tuple and empty frozenset map to different outputs.
    hasher = HasherType()
    _determ_hash(obj, hasher)
    return hasher.intdigest()

def _determ_hash(obj: Hashable, hasher: Hasher) -> None:
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
        hasher.update(obj.to_bytes(
            length=(8 + (i + (i < 0)).bit_length()) // 8,
            byteorder="big",
            signed=True,
        ))
    elif isinstance(obj, float):
        hasher.update(b"float")
        hasher.update(struct.pack("!d", obj))
    elif isinstance(obj, complex):
        hasher.update(b"complex")
        _determ_hash(obj.imag, hasher)
        _determ_hash(obj.real, hasher)
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
        hasher.update("builtinfunctiontype")
        hasher.update(obj.__qualname__.encode())
    elif hasattr(obj, "__determ_hash__"):
        proxy = GetAttr[Callable[[], Any]]()(obj, "__determ_hash__", check_callable=True)()
        hasher.update("__determ_hash__")
        _determ_hash(proxy, hasher)
    else:
        raise TypeError(f"{obj} ({type(obj)}) is not determ_hashable")


def hashable(obj: Any, verbose: bool = False) -> Hashable:
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

    - Picklable objects are hashed as their pickle.dumps.

    - Other objects are hashed as a dict of their attributes.

    """
    if verbose:
        print(f"_hashable({obj}, set(), 0) =")
    ret = _hashable(obj, set(), 0, verbose)
    return ret


attr_blacklist = {
    "__doc__",
    "__weakref__",
    "__dict__", # the actual attributes will get saved
}

def _hashable(obj: Any, tabu: set[int], level: int, verbose: bool) -> Hashable:
    # Make sure I remember to pass tabu and level
    # Make sure I update tabu when I call _determ_hash on a mutable object.
    # I prepend the type if it is a container so that an empty tuple and empty list hash to different keys.

    if level > 50:
        raise ValueError("Maximum recursion")

    print(level*" ", repr(obj), type(obj))
    if isinstance(obj, (type(None), bytes, str, int, float, complex, BuiltinFunctionType)):
        return obj
    elif id(obj) in tabu:
        return b"cycle detected"
    elif isinstance(obj, bytearray):
        return bytes(obj)
    elif isinstance(obj, (tuple, list)):
        tabu = tabu | {id(cast(Any, obj))}
        level = level + 1
        return tuple(
            _hashable(elem, tabu, level, verbose)
            for elem in cast(List[Any], obj)
        )
    elif isinstance(obj, (set, frozenset)):
        tabu = tabu | {id(cast(Any, obj))}
        level = level + 1
        return frozenset(
            _hashable(elem, tabu, level, verbose)
            for elem in cast(Set[Any], obj)
        )
    elif isinstance(obj, dict):
        tabu = tabu | {id(cast(Any, obj))}
        level = level + 1
        return frozenset(
            (key, _hashable(val, tabu, level, verbose))
            for key, val in cast(Dict[Any, Any], obj).items()
        )
    elif hasattr(obj, "__determ_hash__"):
        tabu = tabu | {id(cast(Any, obj))}
        level = level + 1
        proxy = GetAttr[Callable[[], Any]]()(obj, "__determ_hash__", check_callable=True)()
        return _hashable(proxy, tabu, level, verbose)
    elif hasattr(obj, "data") and isinstance(getattr(obj, "data"), memoryview):
        data = GetAttr[memoryview]()(obj, "data")
        return data.tobytes()
    elif isinstance(obj, BuiltinMethodType):
        tabu = tabu | {id(cast(Any, obj))}
        level = level + 1
        return (
            obj.__qualname__,
            _hashable(obj.__self__, tabu, level, verbose),
        )
    elif isinstance(obj, FunctionType):
        closure = inspect.getclosurevars(obj)
        tabu = tabu | {id(obj)}
        level = level + 1
        return (
            obj.__code__.co_code,
            _hashable(obj.__code__.co_consts, tabu, level, verbose),
            _hashable(closure.nonlocals, tabu, level, verbose),
            _hashable(closure.globals, tabu, level, verbose),
        )
    elif isinstance(obj, MethodType):
        tabu = tabu | {id(obj)}
        level = level + 1
        return (
            _hashable(obj.__self__, tabu, level, verbose),
            _hashable(obj.__func__, tabu, level, verbose),
        )
    elif isinstance(obj, Path): # DO NOT COMMIT: uncomment first
        return obj.__fspath__()
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
        attr_names = GetAttr[List[str]]()(obj, "__all__", dir(obj))
        return frozenset(
            (
                (
                    attr_name,
                    _hashable(getattr(obj, attr_name, None), tabu, level, verbose)
                )
                for attr_name in attr_names
            )
        )
    else:
        # if not isinstance(obj, (ModuleType, FunctionType)) and copy.deepcopy(obj) != obj:
        #     raise TypeError("This type isn't equal to its deepcopy; it can't be made hashable")
        # try:
        #     return pickle.dumps(obj, protocol=4)
        # except (pickle.PickleError, AttributeError, TypeError):
        if True:
            tabu = tabu | {id(obj)}
            level = level + 1
            return frozenset(
                (
                    (
                        attr_name,
                        _hashable(getattr(obj, attr_name), tabu, level, verbose),
                    )
                    for attr_name in dir(obj)
                    if all((
                            attr_name not in attr_blacklist,

                            # double check we actually have this attr
                            hasattr(obj, attr_name),

                            # make sure this isn't inherited
                            id(getattr(obj, attr_name)) != id(getattr(type(obj), attr_name, None)),
                    ))
                )
            )
