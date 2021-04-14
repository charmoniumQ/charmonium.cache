from __future__ import annotations
from types import TracebackType
from typing import (
    Protocol,
    Union,
    runtime_checkable,
    Optional,
)


@runtime_checkable
class Lock(Protocol):
    def __enter__(self) -> None:
        ...

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
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


ReadersWriterLockSources = Union[Lock, ReadersWriterLock]


def ReadersWriterLock_from(lock: ReadersWriterLockSources) -> ReadersWriterLock:
    if isinstance(lock, ReadersWriterLock):
        return lock
    else:
        assert isinstance(lock, Lock)
        return NaiveReadersWriterLock(lock)


class NaiveReadersWriterLock(ReadersWriterLock):
    """ReadersWriterLock constructed from a regular Lock.

    A true readers-writers lock permits read concurrency (N readers
    xor 1 writer), but in some cases, that may be more maintanence
    effort than it is worth. A `NaiveReadersWriterLock` permits 1 reader
    xor 1 writer.

    """

    def __init__(self, lock: Lock) -> None:
        self.reader = lock
        self.writer = lock
