from __future__ import annotations
import datetime
from typing import Callable, Any, Union
from pathlib import Path
import os

class FileContents:
    """Use FileContents instead of filenames to make your func pure.

    FileContents is `os.PathLike`_, so you can `open(FileContents("file"))`. You won't even know its not a string :)

    .. _`os.PathLike`: https://docs.python.org/3/library/os.html#os.PathLike

    """

    path: os.PathLike[str]

    def __init__(self, path: Union[str, os.PathLike[str]]) -> None:
        self.path = Path(path) if isinstance(path, str) else path

    def __fspath__(self) -> Union[bytes, str]:
        return self.path.__fspath__()

    def __cache_key__(self) -> str:
        """Returns the path."""
        return str(self.path)

    def __cache_ver__(self) -> bytes:
        """Returns the contents of the file."""
        with open(self.__fspath__(), "rb") as file:
            return file.read()

class TTLInterval:
    """TTLInterval(td)() returns a value that changes once every td.

    Usage:

        >>> from charmonium.cache import *
        >>> @memoized(group=Future(group))
        ... def func():
        ...     pass
        >>> interval = TTLInterval(datetime.timedelta(seconds=5))
        >>> DEFAULT_MEMOIZED_GROUP.fulfill(MemoizedGroup(extra_system_state=interval))  # applies a 5-minute TTL to the whole memoized group

    Or:

        >>> from charmonium.cache import *
        >>> interval = TTLInterval(datetime.timedelta(seconds=5))
        >>> @memoized(extra_func_state=interval) # applies a 5-minute TTL to justthis function
        ... def func():
        ...     pass

    Underlying usage:

        >>> import datetime, time
        >>> interval = TTLInterval(datetime.timedelta(seconds=5))
        >>> start = interval()
        >>> assert start == interval()
        >>> time.sleep(5)
        >>> assert start != interval()

    """
    def __init__(self, interval: datetime.timedelta) -> None:
        self.interval = interval

    def __call__(self, func: Callable[..., Any]) -> int:
        delta = datetime.datetime.now() - datetime.datetime.fromtimestamp(0)
        return delta // self.interval
