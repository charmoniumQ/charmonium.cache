from __future__ import annotations

import datetime
import stat
import zlib
from typing import Any, Callable, Mapping, Tuple, Union, cast

from charmonium.determ_hash import determ_hash

from .pathlike import PathLike, PathLikeFrom, pathlike_from

FILE_COMPARISONS: Mapping[str, Callable[[PathLike], Any]] = {
    "mtime": lambda p: p.stat()[stat.ST_MTIME],
    "crc32": lambda p: zlib.crc32(p.read_bytes()),
    "determ_hash": lambda p: determ_hash(p.read_bytes()),
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

    Since this changes the un/pickle protocol, this class might cause
    unexpected results when used with `fine_grain_persistence`.

    .. |os.PathLike| replace:: ``os.PathLike``
    .. _`os.PathLike`: https://docs.python.org/3/library/os.html#os.PathLike

    """

    path: PathLike
    comparison: str

    def __init__(
        self,
        path: PathLikeFrom,
        comparison: str = "determ_hash",
    ) -> None:
        self.path = pathlike_from(path)
        self.comparison = comparison

    def __add__(self, path: str) -> FileContents:
        new_path = type(self.path)(str(self.path) + path)  # type: ignore
        return FileContents(new_path, self.comparison)

    def __radd__(self, path: str) -> FileContents:
        new_path = type(self.path)(path + str(self.path))  # type: ignore
        return FileContents(new_path, self.comparison)

    def __fspath__(self) -> Union[bytes, str]:
        return self.path.__fspath__()

    def __cache_key__(self) -> str:
        """Returns the path"""
        return str(self.path)

    def __cache_ver__(self) -> Any:
        """Returns the contents of the file"""
        if self.path.exists():
            return FILE_COMPARISONS[self.comparison](self.path)
        else:
            return None

    def __getstate__(self) -> Any:
        """Captures the path and its contents"""
        return (
            self.path,
            self.comparison,
            self.path.read_bytes() if self.path.exists() else b"",
        )

    def __setstate__(self, state: Any) -> None:
        """Restore the contents to the path"""
        self.path, self.comparison, contents = cast(Tuple[PathLike, str, bytes], state)
        self.path.write_bytes(contents)


class TTLInterval:
    """``TTLInterval(td)()`` returns a value that changes once every ``td``.

    ``td`` may be a a timedelta or a number of seconds.

    It can be used as ``extra_system_state`` or
    ``extra_func_state``. For example,

    .. code:: python

        >>> from charmonium.cache import memoize
        >>> interval = TTLInterval(datetime.timedelta(seconds=0.5))
        >>> # applies a 0.5-second TTL to justthis function
        >>> @memoize(extra_func_state=interval)
        ... def func():
        ...     pass

    Underlying usage:

    .. code:: python

        >>> import datetime, time
        >>> interval = TTLInterval(datetime.timedelta(seconds=0.5))
        >>> start = interval()
        >>> start == interval()
        True
        >>> time.sleep(0.5)
        >>> start == interval()
        False

    """

    def __init__(self, interval: Union[int, float, datetime.timedelta]) -> None:
        self.interval = (
            interval
            if isinstance(interval, datetime.timedelta)
            else datetime.timedelta(seconds=interval)
        )

    def __call__(self, func: Any = None) -> int:
        delta = datetime.datetime.now() - datetime.datetime.fromtimestamp(0)
        return delta // self.interval
