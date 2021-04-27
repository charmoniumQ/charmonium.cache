from __future__ import annotations

import datetime
from typing import Any, Union, cast

from .pathlike import PathLike, PathLikeFrom, pathlike_from


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

    def __init__(self, path: PathLikeFrom) -> None:
        self.path = pathlike_from(path)

    def __fspath__(self) -> Union[bytes, str]:
        return self.path.__fspath__()

    def __cache_key__(self) -> str:
        """Returns the path"""
        return str(self.path)

    def __cache_ver__(self) -> bytes:
        """Returns the contents of the file"""
        if self.path.exists():
            return self.path.read_bytes()
        else:
            return b""

    def __getstate__(self) -> Any:
        """Captures the path and its contents"""
        return (self.path, self.path.read_bytes() if self.path.exists() else b"")

    def __setstate__(self, state: Any) -> None:
        """Restore the contents to the path"""
        self.path, contents = cast(tuple[PathLike, bytes], state)
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
