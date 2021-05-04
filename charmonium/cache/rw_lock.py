from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Optional, cast

import attr
import fasteners

from .pathlike import PathLikeFrom, pathlike_from

if TYPE_CHECKING:
    from typing import Protocol

else:
    Protocol = object


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


class RWLock(Protocol):
    """A `Readers-Writer Lock`_ guarantees N readers xor 1 writer.

    This permits read-concurrency in the underlying resource when
    there is no writer.

    .. _`Readers-Writer Lock`: https://en.wikipedia.org/wiki/Readers%E2%80%93writer_lock

    """

    @property
    def reader(self) -> Lock:
        ...

    @property
    def writer(self) -> Lock:
        ...


class NaiveRWLock(RWLock):
    """RWLock constructed from a regular Lock.

    A true readers-writers lock permits read concurrency (N readers
    xor 1 writer), but in some cases, that may be more maintanence
    effort than it is worth. A `NaiveRWLock` permits 1 reader xor 1
    writer.

    """

    def __init__(self, lock: Lock) -> None:
        super().__init__()
        self.lock = lock

    @property
    def reader(self) -> Lock:
        return self.lock

    @property
    def writer(self) -> Lock:
        return self.lock


# pyright thinks attrs has ambiguous overload
@attr.define  # type: ignore
class FileRWLock(RWLock):
    path: PathLikeFrom

    _rw_lock: fasteners.InterProcessReaderWriterLock = attr.ib(init=False)

    def __init__(self, path: PathLikeFrom) -> None:
        """Creates a lockfile at path."""
        super().__init__()
        self.path = pathlike_from(path)
        self._rw_lock = fasteners.InterProcessReaderWriterLock(cast(Path, self.path))

    @property
    def writer(self) -> Lock:
        return self._rw_lock.write_lock()

    @property
    def reader(self) -> Lock:
        return self._rw_lock.read_lock()
