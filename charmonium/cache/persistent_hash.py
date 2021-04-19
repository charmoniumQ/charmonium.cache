import functools
import inspect
import operator
import struct
import sys
import zlib
from pathlib import Path
from types import FunctionType, ModuleType
from typing import Any, Callable, Hashable, cast

from .util import GetAttr

HASH_BITS = 64

def persistent_hash(obj: Any) -> int:
    """A persistent hash protocol.

    The hash is persistent across:
    - different processes
    - different machines
    - different Python versions
    - different OSes

    - Primitive types (bytes, str, int, float, complex, None) are
      hashed by their value or a checksum of their value.

    - Immutable container types (tuple, frozenset) are hashed by the
      XOR of their elements.

    - Objects containing a __persistent_hash__ hashed by calling
      persistent_hash on its return (it need not be an int).

    """
    # Make sure I XOR the typename with the hash of contents. This makes an empty tuple hash differently than an empty dict, avoiding a collision.

    # print(_level*" ", repr(obj))
    if isinstance(obj, type(None)):
        # This way, persistent_hash(None) != persistent_hash(b"").
        return checksum(b"None")
    elif isinstance(obj, bytes):
        return checksum(b"bytes") ^ checksum(obj)
    elif isinstance(obj, str):
        return checksum(b"str") ^ checksum(obj.encode())
    elif isinstance(obj, int):
        # return cheksum(b"int") ^ (obj & ~(1 << HASH_BITS))
        # I use a non-trivial hash to scramble the bits more.
        # The trivial hash function doesn't scramble the residue (x % 2 == 0 implies persistent_hash(x) % 2 == 0), which leads to hash table collisions.
        return checksum(int2bytes(obj))
    elif isinstance(obj, float):
        return checksum(b"float") ^ checksum(float2bytes(obj))
    elif isinstance(obj, complex):
        return checksum(b"complex") ^ checksum(float2bytes(obj.imag)) ^ checksum(float2bytes(obj.real))
    elif isinstance(obj, tuple):
        contents = [persistent_hash(elem) for elem in cast(tuple[Any], obj)]
        return checksum(b"tuple") ^ functools.reduce(operator.xor, contents, 0)
    elif isinstance(obj, frozenset):
        contents = sorted([persistent_hash(elem) for elem in cast(frozenset[Any], obj)])
        return checksum(b"frozenset") ^ functools.reduce(operator.xor, contents, 0)
    elif hasattr(obj, "__persistent_hash__"):
        return checksum(b"persistent_hashable") ^ persistent_hash(GetAttr[Callable[[], Any]]()(obj, "__persistent_hash__")())
    else:
        raise TypeError(f"{obj} ({type(obj)=}) is not persistent_hashable")


def checksum(i: bytes) -> int:
    return zlib.crc32(i)

def int2bytes(i: int) -> bytes:
    return i.to_bytes(length=(8 + (i + (i < 0)).bit_length()) // 8, byteorder='big', signed=True)

def float2bytes(i: float) -> bytes:
    return struct.pack("!d", i)

def hashable(obj: Any) -> Hashable:
    """An injective function that maps anything to a hashable object.

    When given a mutable type, hashable makes an immutable copy of the
    current state.

    The output of this function is also human-readable. It won't
    totally obfuscate debugging.

    Special cases:
    - Objects with `__persistent_hash__` are hashed by making whatever that returns hashable.
    - Modules are hashed by their `__name__` and `__version__`.
    - Functions are hashed by their bytecode, constants, and closure-vars. This means changing comments will not change the hashable value.
    - Other objects are hashed as a dict of their attributes, excluding dunder-attributes.

    """
    old_recursionlimit = sys.getrecursionlimit()
    sys.setrecursionlimit(150)
    ret = _hashable(obj, set(), 0)
    sys.setrecursionlimit(old_recursionlimit)
    return ret

def _hashable(obj: Any, _tabu: set[int], _level: int) -> Hashable:
    # Make sure I remember to pass _tabu and _level
    # Make sure I update _tabu when I call _persistent_hash on a mutable object.
    # I prepend the type if it is a container so that an empty tuple and empty list hash to different keys.

    # print(_level*" ", repr(obj))
    if isinstance(obj, (type(None), bytes, str, int, float, complex)):
        return obj
    elif id(obj) in _tabu:
        return b"cycle detected"
    elif isinstance(obj, tuple):
        return tuple(_hashable(elem, _tabu, _level+1) for elem in cast(tuple[Any], obj))
    elif isinstance(obj, list):
        _tabu = _tabu | {id(cast(Any, obj))}
        return (
            b"list",
            tuple(_hashable(elem, _tabu, _level+1) for elem in cast(list[Any], obj)),
        )
    elif isinstance(obj, frozenset):
        return frozenset(_hashable(elem, _tabu, _level+1) for elem in cast(frozenset[Any], obj))
    elif isinstance(obj, set):
        _tabu = _tabu | {id(cast(Any, obj))}
        return (
            b"set",
            frozenset(_hashable(elem, _tabu, _level+1) for elem in cast(set[Any], obj)),
        )
    elif isinstance(obj, dict):
        _tabu = _tabu | {id(cast(Any, obj))}
        return (
            b"dict",
            frozenset((key, _hashable(val, _tabu, _level+1)) for key, val in cast(dict[Any, Any], obj).items()),
        )
    elif hasattr(obj, "__persistent_hash__"):
        _tabu = _tabu | {id(cast(Any, obj))}
        return _hashable(GetAttr[Callable[[], Any]]()(obj, "__persistent_hash__")(), _tabu, _level+1)
    elif isinstance(obj, ModuleType):
        return (
            obj.__name__,
            _hashable(GetAttr[str]()(obj, "__version__", "", check_callable=False), _tabu, _level+1),
        )
    elif isinstance(obj, Path):
        return (b"Path", obj.__fspath__())
    elif isinstance(obj, FunctionType):
        _tabu = _tabu | {id(cast(Any, obj))}
        func = cast(Callable[..., Any], obj)
        return (
            func.__code__.co_code,
            _hashable(func.__code__.co_consts, _tabu, _level+1),
            _hashable(inspect.getclosurevars(func), _tabu, _level+1),
        )
    else:
        # return _persistent_hash(pickle.dumps(obj), _tabu, _level+1)
        _tabu = _tabu | {id(obj)}
        return (b"obj", _hashable({
            attr_name: getattr(obj, attr_name)
            for attr_name in dir(obj)
            if (not attr_name.startswith('__') # skip dunder methods
                and hasattr(obj, attr_name) # double-check hasattr
                # and (not hasattr(type(obj), attr_name) or not isinstance(getattr(type(obj), attr_name), property)) # skip properties; they might return self
                # and not callable(getattr(obj, attr_name)) # skip callables
            )
        }, _tabu, _level+1))
