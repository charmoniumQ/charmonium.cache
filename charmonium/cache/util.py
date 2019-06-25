from __future__ import annotations
from pathlib import Path
from typing import Hashable, Any, Union, cast, Iterable
import time
import datetime
import urllib.parse
from .types import PathLike


UNIX_TS_ZERO = datetime.datetime(1970, 1, 1)


def to_unix_ts(dtm: datetime.datetime) -> float:
    '''returns the seconds since the Unix epoch for dt'''
    return (dtm - UNIX_TS_ZERO).total_seconds()


def from_unix_ts(unix_ts: float) -> datetime.datetime:
    '''returns the seconds since the Unix epoch for dt'''
    return UNIX_TS_ZERO + datetime.timedelta(seconds=unix_ts)


def unix_ts_now() -> float:
    '''returns the seconds since the Unix epoch'''
    return to_unix_ts(datetime.datetime.now())


def loop_for_duration(duration: float) -> Iterable[float]:
    '''Use in a for loop.

    >>> for t in loop_for_duration(.1):
    ...     print(f'{t:.1} seconds left')
    ...     time.sleep(0.04)
    0.1 seconds left
    0.06 seconds left
    0.02 seconds left
    '''

    start = time.time()
    end = start + duration
    while time.time() < end:
        yield end - time.time()


def to_hashable(obj: Any) -> Hashable:
    '''Converts args and kwargs into a hashable type (overridable)'''
    try:
        hash(obj)
    except TypeError:
        if hasattr(obj, 'items'):
            # turn dictionaries into frozenset((key, val))
            # sorting is necessary to make equal dictionaries map to equal things
            # sorted(..., key=hash)
            return tuple(sorted(
                [(keyf, to_hashable(val)) for keyf, val in obj.items()],
                key=hash
            ))
        elif hasattr(obj, '__iter__'):
            # turn iterables into tuples
            return tuple(to_hashable(val) for val in obj)
        else:
            raise TypeError(f"I don't know how to hash {obj} ({type(obj)})")
    else:
        return cast(Hashable, obj)


def injective_str(obj: Any) -> str:
    '''Safe names are compact, unique, urlsafe, and equal when the objects are equal

str does not work because x == y does not imply str(x) == str(y); it's
not injective.

    >>> a = dict(d=1, e=1)
    >>> b = dict(e=1, d=1)
    >>> a == b
    True
    >>> str(a) == str(b)
    False
    >>> injective_str(a) == injective_str(b)
    True

    '''
    if isinstance(obj, int):
        ret = str(obj)
    elif isinstance(obj, float):
        ret = str(round(obj, 3))
    elif isinstance(obj, str):
        ret = urllib.parse.quote(obj, safe='')
    elif isinstance(obj, list):
        ret = '[' + ','.join(map(injective_str, obj)) + ']'
    elif isinstance(obj, tuple):
        ret = '(' + ','.join(map(injective_str, obj)) + ')'
    elif isinstance(obj, dict):
        ret = '{' + ','.join(sorted(
            injective_str(key) + ':' + injective_str(val)
            for key, val in obj.items()
        )) + '}'
    else:
        raise TypeError()
    return ret


PotentiallyPathLike = Union[PathLike, str, bytes]


def pathify(obj: PotentiallyPathLike) -> PathLike:
    if isinstance(obj, bytes):
        return Path(obj.decode())
    elif isinstance(obj, str):
        return Path(obj)
    elif is_pathlike(obj):
        return obj
    else:
        raise TypeError(f'{obj!r} is not PotentiallyPathLike')

def is_pathlike(obj: Any) -> bool:
    path_attrs = [
        '__truediv__', 'mkdir', 'exists', 'unlink', 'iterdir', 'open', 'parent'
    ]
    return all(hasattr(obj, attr) for attr in path_attrs)


# consider using recursive hashing
def modtime(path: PathLike) -> datetime.datetime:
    if hasattr(path, 'modtime'):
        return getattr(path, 'modtime')()
    elif hasattr(path, 'stat'):
        stat = getattr(path, 'stat')()
        latest_timestamp = max(stat.st_mtime, stat.st_ctime)
        return from_unix_ts(latest_timestamp)
    else:
        raise TypeError(f'Your path type does not support modtime: {path!r}')


def is_dir(path: PathLike) -> bool:
    if hasattr(path, 'is_dir'):
        return cast(bool, getattr(path, 'is_dir')())
    else:
        return False


def modtime_recursive(path: PathLike) -> datetime.datetime:
    if is_dir(path):
        candidates = [modtime(path)] + [modtime_recursive(entry) for entry in path.iterdir()]
        return max(candidates)
    else:
        return modtime(path)
