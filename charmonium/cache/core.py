from __future__ import annotations
import enum
import heapq
import math
import itertools
import random
import logging
import functools
import sys
import pickle as pickle_
import atexit
import contextlib
from pathlib import Path
import datetime
import typing
from typing import (
    Generic,
    TypeVar,
    Callable,
    ContextManager,
    Protocol,
    Optional,
    Any,
    Union,
    cast,
    Final,
    Iterator,
    Iterable,
    Generator,
    TracebackType,
)
from typing_extensions import ParamSpec

import attr
import dill as dill_  # type: ignore

__version__ = "1.0.0"


class Pickler:
    def loads(self, buffer: bytes) -> Any:
        ...

    def dumps(self, val: Any) -> bytes:
        ...


dill = cast(Pickler, dill_)
pickle = cast(Pickler, pickle_)


@typing.runtime_checkable
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


@typing.runtime_checkable
class ReadersWriterLock(Protocol):
    """A [Readers-Writer Lock] guarantees N readers xor 1 writer.

    This permits read-concurrency.

    [Readers-Writer Lock]: https://en.wikipedia.org/wiki/Readers%E2%80%93writer_lock

    """

    read_lock: Lock
    write_lock: Lock


ReadersWriterLockNormalizable = Union[Lock, ReadersWriterLock]


def ReadersWriterLock_from(lock: ReadersWriterLockNormalizable) -> ReadersWriterLock:
    if isinstance(lock, ReadersWriterLock):
        return lock
    else:
        assert isinstance(lock, Lock)
        return NaiveReadersWriterLock(lock)


@typing.runtime_checkable
class PathLike(Protocol):
    """Based on [pathlib.Path]

    [pathlib.Path]: https://docs.python.org/3/library/pathlib.html#pathlib.Path"""

    def __truediv__(self, key: str) -> PathLike:
        """Joins a segment onto this Path."""

    def read_bytes(self) -> bytes:
        ...

    def write_bytes(self, data: bytes) -> int:
        ...


PathLikeNormalizable = Union[str, PathLike]


def PathLike_from(path: PathLikeNormalizable) -> PathLike:
    if isinstance(path, (str)):
        return Path(path)
    else:
        assert isinstance(path, PathLike)
        return path


class Sizeable(Protocol):
    """A protocol for determining storage space usage.

    This way, the storage of the whole can be computed from the size
    of its parts.

    """

    def size(self) -> int:
        ...


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
        with self._lock.read_lock:
            self._data = self._pickler.loads(self._path.read_bytes())

    def write(self) -> None:
        with self._lock.write_lock:
            self._path.write_bytes(self._pickler.dumps(self._data))

    @contextlib.contextmanager
    def read_modify_write(self) -> Generator[None, None, None]:
        with self._lock.write_lock:
            self._data = self._pickler.loads(self._path.read_bytes())
            yield
            self._path.write_bytes(self._pickler.dumps(self._data))

    def items(self) -> Iterable[tuple[tuple[Any, ...], Any]]:
        for key, val in self._data.items(len(self.schema) + 1):
            yield (key[1:], val)


class ObjStore(Sizeable, Generic[Key, Val]):
    def __setitem__(self, key: Key, val: Val) -> None:
        ...

    def __getitem__(self, key: Key) -> Val:
        ...

    def __delitem__(self, key: Key) -> None:
        ...


class KeyGen:
    """Generates unique keys (not cryptographically secure)."""

    def __init__(self, key_bits: int) -> None:
        self.key_bits = key_bits
        self.key_bytes = int(math.ceil(key_bits / 8))
        self.key_space = 2 ** self.key_bits

    def __iter__(self) -> KeyGen:
        return self

    def __next__(self) -> int:
        """Generates a new key."""
        return random.randint(0, 2 ** self.key_space - 1)

    def probability_of_collision(self, keys: int) -> float:
        """Use to assert the probability of collision is acceptable."""
        try:
            import scipy  # type: ignore
        except ImportError:
            raise ImportError("I require scipy to compute probability_of_collision")
        return 1 - cast(
            float, scipy.special.perm(self.key_space, keys, exact=False)  # type: ignore
        ) / (self.key_space ** keys)


T = TypeVar("T")


@attr.s  # type: ignore
class Entry(Generic[T]):
    data_size: int
    compute_time: float
    obj_store: bool
    last_use: datetime.datetime
    value: T


class NaiveReadersWriterLock(ReadersWriterLock):
    """ReadersWriterLock constructed from a regular Lock.

    A true readers-writers lock permits read concurrency (N readers
    xor 1 writer), but in some cases, that may be more maintanence
    effort than it is worth. A `NaiveReadersWriterLock` permits 1 reader
    xor 1 writer.

    """

    def __init__(self, lock: Lock) -> None:
        self.lock = lock

    @property
    def read_lock(self) -> Lock:
        return self.lock

    @property
    def write_lock(self) -> Lock:
        return self.lock


FuncParams = ParamSpec("FuncParams")
FuncReturn = TypeVar("FuncReturn")


def constant(val: Val) -> Callable[..., Val]:
    def fn(*args: Any, **kwargs: Any) -> Val:
        return val

    return fn


BYTE_ORDER: Final[str] = "big"


def memoize(
    **kwargs: Any,
) -> Callable[[Callable[FuncParams, FuncReturn]], Callable[FuncParams, FuncReturn]]:
    def actual_memoize(
        func: Callable[FuncParams, FuncReturn], /
    ) -> Callable[FuncParams, FuncReturn]:
        return Memoize[FuncParams, FuncReturn](func, **kwargs)

    return actual_memoize


def LUV(entry: Entry[Any]) -> float:
    return 0


@attr.s  # type: ignore
class MemoizedGroup:
    _index: Index

    _obj_store: ObjStore[int, bytes]

    _key_gen: KeyGen = attr.ib(default_factory=KeyGen)  # type: ignore

    _size: int = attr.ib(default=1 * 1024 * 1024)

    _pickler: Pickler = attr.ib(default=pickle)

    _verbose: bool = attr.ib(default=True)

    def __init__(self) -> None:
        self._index.read()
        atexit.register(self._index.write)

    _extra_global_state: Callable[[], Any] = attr.ib(default=constant(None))

    def _global_state(self) -> Any:
        """Functions are deterministic with (global state, function-specific state, args key, args version).

        - The global_state contains:
          - Package version

        """
        return (__version__, self._extra_global_state())

    _eval_func: Callable[[Entry[Any]], float] = attr.ib(default=LUV)

    def _evict(self) -> None:
        heap = list[tuple[float, tuple[Any, ...], Entry[Any]]]()
        for key, entry in self._index.items():
            heapq.heappush(heap, (self._eval_func(entry), key, entry))
        while self._index.size() + self._obj_store.size() > self._size:
            _, key, entry = heap.pop()
            if entry.obj_store:
                del self._obj_store[entry.value]
            del self._index[key]

    _use_count: Iterator[int] = itertools.count()


class Sentinel:
    pass


class Future(Generic[T]):
    """Represents a future value that has not yet been computed."""

    # TODO: create_future(Callable[[], T]) -> T: ...

    empty_result_sentinel = Sentinel()

    def __init__(
        self,
        result: Union[T, Sentinel] = empty_result_sentinel,
        result_thunk: Optional[Callable[[], T]] = None,
    ) -> None:
        """
        :param result: supply if you intend to fulfill the Future right away.
        """
        self.result: Union[T, Sentinel] = result
        self.result_thunk = result_thunk
        if self.is_fulfilled and self.result_thunk:
            raise ValueError("Cannot supply a result and a result_thunk")

    @property
    def is_fulfilled(self) -> bool:
        return self.result != Future.empty_result_sentinel or self.result_thunk is not None

    def fulfill(self, result: T) -> None:
        if self.is_fulfilled:
            raise ValueError("Future is already fulfilled.")
        self.result = result

    @property
    def _(self) -> T:
        """Returns the value, and ValueErrors if it is not yet fulfilled."""
        if not self.is_fulfilled:
            raise ValueError("Future is not yet fulfilled.")
        else:
            if self.result == Future.empty_result_sentinel:
                self._result = self._result_thunk()
            return self._result

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._, attr)


DEFAULT_MEMOIZED_GROUP = Future[MemoizedGroup]()


@attr.s  # type: ignore
class Memoize(Generic[FuncParams, FuncReturn]):
    def __attrs_post_init__(self) -> None:
        functools.update_wrapper(self, self._func)
        self._name = f"{self._func.__module__}.{self._func.__qualname__}"
        self._logger = logging.getLogger("charmonium.cache").getChild(self._name)
        self._logger.setLevel(logging.DEBUG)
        self._handler = logging.StreamHandler(sys.stderr)
        self._handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
        if self._verbose:
            self.enable_logging()

    _func: Callable[FuncParams, FuncReturn]

    _group: MemoizedGroup = attr.ib()

    _name: Optional[str] = attr.ib(default=None)

    # TODO: make this accept default_group_verbose = Sentinel()
    _verbose: bool = attr.ib(default=True)

    _apply_obj_store: Callable[FuncParams, bool] = attr.ib(default=constant(True))

    # TODO: make this accept default_group_pickler = Sentinel()
    _pickler: Pickler = attr.ib(default=pickle)

    _fine_grain_eviction: bool = attr.ib(default=False)
    _fine_grain_persistence: bool = attr.ib(default=False)

    _extra_func_state: Callable[[Callable[FuncParams, FuncReturn]], Any] = attr.ib(
        default=constant(None)
    )

    def _func_state(self) -> Any:
        """Returns function-specific state.

        See _global_state for the usage of function-specific state.

        - The function state contains:
          - the source code, the
          - closed-over vars
          - memoization configuration
          - `func.__version__()`
          - `extra_func_state(func)`

        - I provide no `clear()` method to clear the cache, because
          you can just increment the func state to get the same
          effect.

        """
        return (
            dill.dumps(self._func),
            self._pickler,
            self._group._obj_store,
            cast(Callable[[], Any], getattr(self._func, "__version__", lambda: None))(),
            self._extra_func_state(self._func),
        )

    _extra_args2key: Callable[FuncParams, FuncReturn] = cast(
        Callable[FuncParams, FuncReturn], attr.ib(default=constant(None))
    )

    def _args2key(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> Any:
        """Convert arguments to their key for caching.

        - The cache uses the "args key" to mean "this is the same
          resource but possibly a different version." If the "args
          key" is the same, then "args version" assesses if the
          verison is new. For arguments which are not versioned
          resources, using that argument as the key and a constant as
          the version (e.g. `"1.0.0"`) will work. This is the
          default."

        - The args2key consists of the default and the
          `extra_args2key(*args, **kwargs)`. The default is
          `obj.__cache_key__()` if it exists and `obj` otherwise.

        - Therefore, this can be customized two ways: by
          `obj.__cache_key__()` and `extra_args2key`. If you can
          modify the type, prefer adding `__cache_key__` over adding
          `extra_args2key`. This is will be used universally when you
          use that type, and you don't have to "remember" to add the
          args2key.

        """
        return (
            {
                key: cast(Callable[[], Any], getattr(val, "__cache_key__", lambda: val))()
                for key, val in {**dict(enumerate(args)), **kwargs}.items()
            },
            self._extra_args2key(*args, **kwargs),
        )

    _extra_args2ver: Callable[FuncParams, FuncReturn] = cast(
        Callable[FuncParams, FuncReturn], attr.ib(default=constant(None))
    )

    def _args2ver(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> Any:
        """Convert arguments to their version for caching.

        - See `args2key`. The version consists of the default and
          `extra_args2ver`. The default is `obj.__cache_ver__()` if it
          exists and None (no version) otherwise. Prefer to change
          `__cache_ver__` rather than `extra_args2ver`.

        """
        return (
            {
                key: cast(Callable[[], None], getattr(val, "__cache_key__", lambda: val))()
                for key, val in {**dict(enumerate(args)), **kwargs}.items()
            },
            self._extra_args2ver(*args, **kwargs),
        )

    def enable_logging(self) -> None:
        self._logger.addHandler(self._handler)

    def disable_logging(self) -> None:
        self._logger.removeHandler(self._handler)

    def __str__(self) -> str:
        return f"memoized {self._name}"

    def _recompute(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs,) -> Entry[FuncReturn]:
        start = datetime.datetime.now()
        value = self._func(*args, **kwargs)
        stop = datetime.datetime.now()

        value_ser = self._pickler.dumps(value)
        data_size = len(value_ser)
        apply_obj_store = self._apply_obj_store(*args, **kwargs)
        if apply_obj_store:
            key = next(self._group._key_gen)
            self._group._obj_store[key] = value_ser
            value_ser = key.to_bytes(self._group._key_gen.key_bytes, BYTE_ORDER)
            data_size += len(value_ser)

        return Entry[FuncReturn](
            data_size=data_size, compute_time=stop - start, value=value, obj_store=apply_obj_store,
        )

    def __call__(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> FuncReturn:
        # TODO: capture overhead. Warn and log based on it.

        key = (
            self._group._global_state(),
            self._name,
            self._func_state(),
            self._args2key(*args, **kwargs),
            self._args2ver(*args, **kwargs),
        )

        if self._fine_grain_persistence:
            self._group._index.read()

        entry = self._group._index.get_or(key, self._recompute)
        entry.size += len(self._pickler.dumps(key))
        entry.last_use = datetime.datetime.now()
        entry.last_use_count = next(self._group._use_count)

        if self._fine_grain_persistence:
            with self._group._index.read_modify_write():
                self._group._evict()

        if self._fine_grain_eviction:
            self._group._evict()

        value_ser = entry.value
        if entry.obj_store:
            key = int.from_bytes(value_ser, BYTE_ORDER)
            value_ser = self._group._obj_store[key]
        value: FuncReturn = self._pickler.loads(value_ser)
        # TODO: figure out how to elide this `loads(dumps(...))`, if we did a recompute.

        return value


# TODO: thread safety
