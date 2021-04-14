from __future__ import annotations
import enum
import contextlib
from pathlib import Path
from typing import (
    Generic,
    Generator,
    TypeVar,
    Callable,
    ContextManager,
    Protocol,
    Any,
    Iterable,
)

import attr

from .util import Sizeable, Pickler, PathLike, PathLike_from, pickle
from .readers_writer_lock import ReadersWriterLock, ReadersWriterLock_from


class IndexKeyType(enum.IntEnum):
    MATCH = 0
    LOOKUP = 1


class Index(Sizeable, Protocol):

    initialized: bool
    # TODO: instance-var doc-string: Returns if data is in the Index from read()

    schema: tuple[IndexKeyType]

    def __init__(self, schema: tuple[IndexKeyType]) -> None:
        self.schema = schema

    def __delitem__(self, keys: tuple[Any, ...]) -> None:
        ...

    def get_or(self, keys: tuple[Any, ...], thunk: Callable[[], Any]) -> Any:
        """Gets the value at `key` or calls `thunk` and stores it at `key`."""

    def items(self) -> Iterable[tuple[tuple[Any, ...], Any]]:
        ...

    def read(self) -> None:
        """Atomically read index from storage.

        The mechanism of locking could depend on the storage medium
        used by the Index implementation. For example, this may use
        file locks or database transactions.

        If the cache is never used by multiple processes, the lock can
        be omitted entirely.

        """

    def write(self) -> None:
        """Atomic write index from storage.

        See the note on read.

        """

    def read_modify_write(self) -> ContextManager[None]:
        """Atomic RMW, where the modification is done by the ContextManager.

        See the note on read.

        """


Key = TypeVar("Key")
Val = TypeVar("Val")


class DictIndex(Generic[Key, Val]):
    def __init__(self, single_key: bool = False) -> None:
        self.single_key = single_key
        self.data = dict[Key, Val]()

    def __delitem__(self, key: Key) -> None:
        del self.data[key]

    def __contains__(self, key: Key) -> bool:
        return key in self

    def get_or(self, key: Key, thunk: Callable[[], Val]) -> Val:
        if key in self.data:
            return self.data[key]
        else:
            if self.single_key:
                self.data.clear()
            val = thunk()
            self.data[key] = val
            return val

    def update(self, other: DictIndex[Key, Val], depth: int) -> None:
        for key_, val in other.items(0):
            key = key_[0]
            if key in self.data and depth > 0:
                self.data[key].update(val, depth - 1)  # type: ignore
            else:
                if self.single_key:
                    self.data.clear()
                self.data[key] = val

    def items(self, depth: int) -> Iterable[tuple[tuple[Any, ...], Val]]:
        if depth <= 0:
            for key, val in self.data.items():
                yield ((key,), val)
        else:
            for key, val in self.data.items():
                for subkey, subval in val.items(depth - 1):  # type: ignore
                    yield (key + subkey, subval)


@attr.s  # type: ignore
class FileIndex(Index):
    def __init__(self, schema: tuple[IndexKeyType]) -> None:
        self.schema = schema
        self._data = DictIndex[Any, Any](single_key=True)

    _path: PathLike = attr.ib(default=PathLike_from(Path(".cache")))
    _lock: ReadersWriterLock = attr.ib(default=ReadersWriterLock_from(contextlib.nullcontext()))
    _pickler: Pickler = attr.ib(default=pickle)
    # Two ways to implement _data:
    # - a hierarchical dict (dict of dict of dicts of ...)
    # - or a mixed-key dict.(keys are k1 or (k1, k2) or (k1, k2, k3))
    # Either way, the typing system can't handle it.
    # The hierarchical dict makes it easier to delete stuff.
    # Suppose I need to delete (k1, k2, *, *, *).
    # In the hierarchical dict, I drop `del _data[k1][k2]`.
    # In the mixed-key dict, I need to iterate over and remove all keys beginning with (k1, k2).

    def get_or(self, keys: tuple[Any, ...], thunk: Callable[[], Any]) -> Any:
        if len(keys) != len(self.schema):
            raise ValueError("{keys=} do not match {self.schema=}")
        obj = self._data
        for next_key_schema, key in zip(self.schema + (None,), (None,) + keys):
            single_key = next_key_schema == IndexKeyType.MATCH
            this_thunk = (
                (lambda: DictIndex[Any, Any](single_key=single_key))
                if next_key_schema is not None
                else thunk
            )
            obj = obj.get_or(key, this_thunk)
        return obj

    def __delitem__(self, keys: tuple[Any, ...]) -> None:
        obj = self._data
        for key in (None,) + keys:
            if key not in obj:
                break
            obj = obj.get_or(key, lambda: None)
        del obj[keys[-1]]

    def read(self) -> None:
        with self._lock.reader:
            self._data = self._pickler.loads(self._path.read_bytes())

    def write(self) -> None:
        with self._lock.writer:
            self._path.write_bytes(self._pickler.dumps(self._data))

    @contextlib.contextmanager
    def read_modify_write(self) -> Generator[None, None, None]:
        with self._lock.writer:
            self._data = self._pickler.loads(self._path.read_bytes())
            yield
            self._path.write_bytes(self._pickler.dumps(self._data))

    def items(self) -> Iterable[tuple[tuple[Any, ...], Any]]:
        for key, val in self._data.items(len(self.schema) + 1):
            yield (key[1:], val)
