from __future__ import annotations

import datetime
from typing import Any, Union

from .util import PathLike, PathLikeFrom, pathlike_from


class FileContents:
    """Use FileContents instead of filenames to make your func pure.

    FileContents is `os.PathLike`_, so you can `open(FileContents("file"))`. You won't even know its not a string :)

    .. _`os.PathLike`: https://docs.python.org/3/library/os.html#os.PathLike

    """

    path: PathLike

    def __init__(self, path: PathLikeFrom) -> None:
        self.path = pathlike_from(path)

    def __fspath__(self) -> Union[bytes, str]:
        return self.path.__fspath__()

    def __cache_key__(self) -> str:
        """Returns the path."""
        return str(self.path)

    def __cache_ver__(self) -> bytes:
        """Returns the contents of the file."""
        if self.path.exists():
            return self.path.read_bytes()
        else:
            return b""

class TTLInterval:
    """TTLInterval(td)() returns a value that changes once every td.

    MemoizedGroup usage:

        >>> from charmonium.cache import memoize, Future, DEFAULT_MEMOIZED_GROUP, MemoizedGroup
        >>> # applies a 5-minute TTL to the whole memoized group
        >>> @memoize()
        ... def func():
        ...     pass
        >>> interval = TTLInterval(datetime.timedelta(seconds=0.1))
        >>> DEFAULT_MEMOIZED_GROUP.fulfill(MemoizedGroup(extra_system_state=interval))

    Memoized usage:

        >>> interval = TTLInterval(datetime.timedelta(seconds=0.1))
        >>> # applies a 5-minute TTL to justthis function
        >>> @memoize(extra_func_state=interval)
        ... def func():
        ...     pass

    Underlying usage:

        >>> import datetime, time
        >>> interval = TTLInterval(datetime.timedelta(seconds=0.01))
        >>> start = interval()
        >>> start == interval()
        True
        >>> time.sleep(0.01)
        >>> start == interval()
        False

    """
    def __init__(self, interval: datetime.timedelta) -> None:
        self.interval = interval

    def __call__(self, func: Any=None) -> int:
        delta = datetime.datetime.now() - datetime.datetime.fromtimestamp(0)
        return delta // self.interval
