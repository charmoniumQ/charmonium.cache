from __future__ import annotations

from types import TracebackType
from typing import Optional, Protocol, runtime_checkable

import attr
import fasteners

from .util import PathLikeFrom, pathlike_from


@runtime_checkable
class Lock(Protocol):
    def __enter__(self) -> Optional[bool]:
        ...

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        ...


@runtime_checkable
class ReadersWriterLock(Protocol):
    """A [Readers-Writer Lock] guarantees N readers xor 1 writer.

    This permits read-concurrency.

    [Readers-Writer Lock]: https://en.wikipedia.org/wiki/Readers%E2%80%93writer_lock

    """

    reader: Lock
    writer: Lock


class NaiveReadersWriterLock(ReadersWriterLock):
    """ReadersWriterLock constructed from a regular Lock.

    A true readers-writers lock permits read concurrency (N readers
    xor 1 writer), but in some cases, that may be more maintanence
    effort than it is worth. A `NaiveReadersWriterLock` permits 1 reader
    xor 1 writer.

    """

    def __init__(self, lock: Lock) -> None:
        super().__init__()
        self.reader = lock
        self.writer = lock


# pyright thinks attrs has ambiguous overload
@attr.frozen  # type: ignore
class FastenerReadersWriterLock:
    # pyright doesn't limit the domain of converter, hence type ignore
    path: PathLikeFrom = attr.ib(converter=pathlike_from)  # type: ignore

    _rw_lock: fasteners.InterProcessReaderWriterLock = attr.ib(init=False)

    def __attrs_post_init__(self) -> None:
        object.__setattr__(
            self, "_rw_lock", fasteners.InterProcessReaderWriterLock(str(self.path))
        )

    @property
    def writer(self) -> Lock:
        return self._rw_lock.write_lock()

    @property
    def reader(self) -> Lock:
        return self._rw_lock.read_lock()
