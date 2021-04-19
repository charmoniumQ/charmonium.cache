import functools
import operator
import pickle
import struct
import zlib
from types import ModuleType
from typing import Any, Callable, Iterable, cast, Hashable

from .util import GetAttr

HASH_BITS = 32

def persistent_hash(obj: Any) -> int:
    """A persistent hash protocol.

    The hash is persistent across:
    - different processes
    - different machines
    - different Python versions
    - different OSes

    - Primitive types (bytes, str, int, float, complex, None) are
      hashed by their value or a checksum of their value.

    - Container types (tuple, list, set, frozenset) are hashed by the
      XOR of their elements.

    - Objects containing a __persistent_hash__ hashed by calling
      persistent_hash on its return (it need not be an int).

    - Modules are hashed by their __name__ and __version__ (if
      exists).

    - Other objects are hashed by their non-callable attributes.


    If the default behavior doesn't work for your object, try
    returning a serialization of your object. That is more often
    correct but also slower (hence not the default). If some other
    serialization works better than pickle, use that instead.

    .. code:: python
        class Foo:
            ...
            def __persistent_hash__(self):
                return pickle.dumps(self)

    """
    return _persistent_hash(obj, set(), 0)

def _persistent_hash(obj: Any, _tabu: set[int], _level: int) -> int:
    # Make sure I don't recurse into persistent_hash (don't forget an underscore)
    # Make sure I remember to pass _tabu
    # Make sure I update _tabu when I call _persistent_hash on a mutable object.

    # print(_level*" ", obj)
    if isinstance(obj, type(None)):
        return 0
    elif isinstance(obj, bytes):
        return zlib.crc32(obj)
    elif isinstance(obj, str):
        return _persistent_hash(obj.encode(), _tabu, _level+1)
    elif isinstance(obj, int):
        return obj & ~(1 << HASH_BITS)
    elif isinstance(obj, float):
        return _persistent_hash(struct.pack("!d", obj), _tabu, _level+1)
    elif isinstance(obj, complex):
        return _persistent_hash(obj.imag, _tabu, _level+1) ^ _persistent_hash(obj.real, _tabu, _level+1)
    elif id(obj) in _tabu:
        return 0
    elif isinstance(obj, tuple):
        contents = [_persistent_hash(elem, _tabu, _level+1) for elem in obj]
        return functools.reduce(operator.xor, contents, 0)
    elif isinstance(obj, frozenset):
        contents = sorted([_persistent_hash(elem, _tabu, _level+1) for elem in obj])
        return functools.reduce(operator.xor, contents, 0)
    elif isinstance(obj, list):
        # these datatypes are mutable, so they can contain themselves
        # e.g.
        #
        #     >>> a = [1]
        #     >>> a.append(a)
        #     >>> a
        #     [1, [...]]
        #
        # Therefore, I will add them to the tabu list.
        _tabu = _tabu | {id(obj)}
        contents = [_persistent_hash(elem, _tabu, _level+1) for elem in obj]
        return functools.reduce(operator.xor, contents, 0)
    elif isinstance(obj, set):
        _tabu = _tabu | {id(obj)}
        contents = sorted([_persistent_hash(elem, _tabu, _level+1) for elem in obj])
        return functools.reduce(operator.xor, contents, 0)
    elif isinstance(obj, dict):
        _tabu = _tabu | {id(obj)}
        contents = sorted(_persistent_hash(item, _tabu, _level+1) for item in cast(dict[Any, Any], obj).items())
        return functools.reduce(operator.xor, contents, 0)
    elif hasattr(obj, "__persistent_hash__"):
        _tabu = _tabu | {id(obj)}
        return _persistent_hash(GetAttr[Callable[[], Any]]()(obj, "__persistent_hash__")(), _tabu, _level+1)
    elif isinstance(obj, ModuleType):
        return _persistent_hash((obj.__name__, GetAttr[str]()(obj, "__version__", "", check_callable=False)), _tabu, _level+1)
    else:
        return _persistent_hash(pickle.dumps(obj), _tabu, _level+1)
        # _tabu = _tabu | {id(obj)}
        # return _persistent_hash({
        #     attr_name: getattr(obj, attr_name)
        #     for attr_name in dir(obj)
        #     if not attr_name.startswith('__') and hasattr(obj, attr_name) and not callable(getattr(obj, attr_name))
        # }, _tabu, _level+1)

def hashable(obj: Any) -> Hashable:
    return _hashable(obj, set())

def _hashable(obj: Any, _tabu: set[int]) -> Hashable:
    if isinstance(obj, (type(None), bytes, str, int, float, complex)):
        return obj
    elif id(obj) in _tabu:
        return 0
    elif isinstance(obj, tuple):
        return tuple(_hashable(elem, _tabu) for elem in obj)
    elif isinstance(obj, list):
        _tabu = _tabu | {id(obj)}
        return tuple(_hashable(elem, _tabu) for elem in obj)
    elif isinstance(obj, frozenset):
        return frozenset(_hashable(elem, _tabu) for elem in obj)
    elif isinstance(obj, set):
        _tabu = _tabu | {id(obj)}
        return frozenset(_hashable(elem, _tabu) for elem in obj)
    elif isinstance(obj, dict):
        _tabu = _tabu | {id(obj)}
        return frozenset((key, _hashable(val, _tabu)) for key, val in cast(dict[Any, Any], obj).items())
    elif hasattr(obj, "__persistent_hash__"):
        _tabu = _tabu | {id(obj)}
        return _hashable(GetAttr[Callable[[], Any]]()(obj, "__persistent_hash__")(), _tabu)
    elif isinstance(obj, ModuleType):
        _tabu = _tabu | {id(obj)}
        return _hashable((obj.__name__, GetAttr[str]()(obj, "__version__", "", check_callable=False)), _tabu)
    else:
        return pickle.dumps(obj)
        # _tabu = _tabu | {id(obj)}
        # return _hashable({
        #     attr_name: getattr(obj, attr_name)
        #     for attr_name in dir(obj)
        #     if not attr_name.startswith('__') and hasattr(obj, attr_name) and not callable(getattr(obj, attr_name))
        # }, _tabu)
