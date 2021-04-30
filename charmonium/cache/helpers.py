from __future__ import annotations

import datetime
import stat
import zlib
from typing import Any, Callable, Mapping, Tuple, Union, cast

import attr

from .pathlike import PathLike, PathLikeFrom, pathlike_from

FILE_COMPARISONS: Mapping[str, Callable[[PathLike], Any]] = {
    "mtime": lambda p: p.stat()[stat.ST_MTIME] if p.exists() else None,
    "crc32": lambda p: zlib.crc32(p.read_bytes()) if p.exists() else None,
}


class FileContents:
    """wraps the path and its contents, to make your function pure

    - When FileContents is un/pickled, the contents of path get
      restored/snapshotted.

    - When FileContents is used as an argument, the path is the key
      and the contents are the version.

    FileContents is |os.PathLike|_, so you can
    ``open(FileContents("file"), "rb")``. You won't even know its not
    a string.

    .. |os.PathLike| replace:: ``os.PathLike``
    .. _`os.PathLike`: https://docs.python.org/3/library/os.html#os.PathLike

    """

    path: PathLike
    comparison: Callable[[PathLike], Any]

    def __init__(self, path: PathLikeFrom, comparison: Union[str, Callable[[PathLike], Any]] = "crc32") -> None:
        self.path = pathlike_from(path)
        self.comparison = comparison if callable(comparison) else FILE_COMPARISONS[comparison]

    def __add__(self, path: str) -> FileContents:
        new_path = type(self.path)(str(self.path) + path) # type: ignore
        return FileContents(new_path, self.comparison)

    def __radd__(self, path: str) -> FileContents:
        new_path = type(self.path)(path + str(self.path)) # type: ignore
        return FileContents(new_path, self.comparison)

    def __fspath__(self) -> Union[bytes, str]:
        return self.path.__fspath__()

    def __cache_key__(self) -> str:
        """Returns the path"""
        return str(self.path)

    def __cache_ver__(self) -> Any:
        """Returns the contents of the file"""
        return self.comparison(self.path)

    def __getstate__(self) -> Any:
        """Captures the path and its contents"""
        return (self.path, self.path.read_bytes() if self.path.exists() else b"")

    def __setstate__(self, state: Any) -> None:
        """Restore the contents to the path"""
        self.path, contents = cast(Tuple[PathLike, bytes], state)
        self.path.write_bytes(contents)


class TTLInterval:
    """``TTLInterval(td)()`` returns a value that changes once every ``td``.

    ``td`` may be a a timedelta or a number of seconds.

    It can be used as ``extra_system_state`` or
    ``extra_func_state``. For example,

    .. code:: python

        >>> from charmonium.cache import memoize
        >>> interval = TTLInterval(datetime.timedelta(seconds=0.1))
        >>> # applies a 5-minute TTL to justthis function
        >>> @memoize(extra_func_state=interval)
        ... def func():
        ...     pass

    Underlying usage:

    .. code:: python

        >>> import datetime, time
        >>> interval = TTLInterval(datetime.timedelta(seconds=0.01))
        >>> start = interval()
        >>> start == interval()
        True
        >>> time.sleep(0.01)
        >>> start == interval()
        False

    """

    def __init__(self, interval: Union[int, float, datetime.timedelta]) -> None:
        self.interval = interval if isinstance(interval, datetime.timedelta) else datetime.timedelta(seconds=interval)

    def __call__(self, func: Any=None) -> int:
        delta = datetime.datetime.now() - datetime.datetime.fromtimestamp(0)
        return delta // self.interval


# TODO: docs, testing
@attr.frozen()  # type: ignore
class KeyVer:
    key: str
    ver: str
    def __cache_key__(self) -> str:
        return self.key
    def __cache_ver__(self) -> str:
        return self.ver
