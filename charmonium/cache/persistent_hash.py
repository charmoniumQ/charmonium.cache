import functools
import operator
import struct
import zlib
from typing import Any, Callable, Iterable, cast

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
    if obj is None:
        return 0
    elif isinstance(obj, bytes):
        return zlib.crc32(obj)
    elif isinstance(obj, str):
        return persistent_hash(obj.encode())
    elif isinstance(obj, int):
        return obj & ~(1 << HASH_BITS)
    elif isinstance(obj, float):
        return persistent_hash(struct.pack("!f", obj))
    elif isinstance(obj, complex):
        return persistent_hash(obj.imag) ^ persistent_hash(obj.real)
    elif isinstance(obj, (tuple, list, set, frozenset)):
        contents = map(persistent_hash, cast(Iterable[Any], obj))
        return functools.reduce(operator.xor, contents, 0)
    elif isinstance(obj, (dict)):
        contents = (
            persistent_hash(key) ^ persistent_hash(val)
            for key, val in cast(dict[Any, Any], obj).items()
        )
        return functools.reduce(operator.xor, contents, 0)
    elif hasattr(obj, "__persistent_hash__"):
        return persistent_hash(GetAttr[Callable[[], Any]]()(obj, "__persistent_hash__")())
    else:
        return persistent_hash({
            attr_name: getattr(obj, attr_name)
            for attr_name in dir(obj)
            if not attr_name.startswith('__') and not callable(getattr(obj, attr_name))
        })
