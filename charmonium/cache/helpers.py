import datetime

import attr

from .util import PathLikeFrom, pathlike_from


class FileContents:
    path: PathLike

    def __init__(self, path: PathLikeFrom) -> None:
        self.path = pathlike_from(path)

    def __cache_key__(self) -> str:
        """Returns the path."""
        return str(self.path)

    def __cache_val__(self) -> bytes:
        """Returns the contents of the file."""
        return self.path.read_bytes()

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

    def __call__(self) -> datetime.datetime:
        delta = datetime.datetime.now() - datetime.datetime.fromtimestamp(0)
        return delta // self.interval
