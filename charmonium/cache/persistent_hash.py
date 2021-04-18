import functools
import struct
import operator
from typing import Any, cast, Iterable, Callable
import zlib

from .util import GetAttr

HASH_BITS = 32

def persistent_hash(obj: Any) -> int:
    if isinstance(obj, bytes):
        return zlib.crc32(obj)
    elif isinstance(obj, str):
        return persistent_hash(obj.encode())
    elif isinstance(obj, int):
        return obj & ~(1 << HASH_BITS)
    elif isinstance(obj, float):
        return persistent_hash(struct.pack("!f", obj))
    elif isinstance(obj, (tuple, list, set, frozenset)):
        return functools.reduce(operator.xor, map(persistent_hash, cast(Iterable[Any], obj)), 0)
    elif isinstance(obj, (dict)):
        return persistent_hash(list(cast(dict[Any, Any], obj).items()))
    elif hasattr(obj, "__persistent_hash__"):
        return persistent_hash(GetAttr[Callable[[], Any]]()(obj, "__persistent_hash__")())
    else:
        # return persistent_hash(pickle.dumps(obj))
        return persistent_hash({
            attr_name: getattr(obj, attr_name)
            for attr_name in dir(obj)
            if not attr_name.startswith('__') and not callable(getattr(obj, attr_name))
        })

                
