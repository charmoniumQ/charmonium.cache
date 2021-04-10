import enum
import random
import logging
import functools
import sys
import pickle
import atexit
import contextlib
from pathlib import PurePath, Path
import datetime
import typing
import inspect
from typing import Generic, TypeVar, Iterator, Callable, ContextManager, Protocol, Optional, Any, ParamSpec, Union, cast
import attr

__version__ = "1.0.0"

@typing.runtime_checkable
class Lock(ContextManager[None]):
    ...

@typing.runtime_checkable
class ReadersWriterLock(Protocol):
    """A [Readers-Writer Lock] guarantees N readers xor 1 writer.

    This permits read-concurrency.

    [Readers-Writer Lock]: https://en.wikipedia.org/wiki/Readers%E2%80%93writer_lock

    """
    def read_locked(self) -> Lock: ...
    def write_locked(self) -> Lock: ...

    # Input = Union[Lock, ReadersWriterLock]

    # @staticmethod
    # def normalize(lock: ReadersWriterLock.Input) -> ReadersWriterLock:
    #     if isinstance(lock, ReadersWriterLock):
    #         return lock
    #     elif isinstance(lock, Lock):
    #         return NaiveReadersWriterLock(lock)
    #     else:
    #         raise TypeError(f"Don't know how to make a ReadersWriterLock out of {type(lock)} {lock}")

@typing.runtime_checkable
class PathLike(Protocol):
    """Based on [pathlib.Path]

    [pathlib.Path]: https://docs.python.org/3/library/pathlib.html#pathlib.Path"""

    # Input = Union[str, PathLike]

    # @staticmethod
    # def normalize(path: PathLike.Input) -> PathLike:
    #     if isinstance(path, (str)):
    #         return Path(path)
    #     elif isinstance(path, PathLike):
    #         return path
    #     else:
    #         raise TypeError(f"Don't know how to make a PathLike out of {type(path)} {path}")

    def __truediv__(self, other: Union[str, PurePath]) -> PathLike:
        """Joins a segment onto this Path."""

    def read_bytes(self) -> bytes: ...

    def write_bytes(self, buffer: bytes) -> int: ...

class Sizeable(Protocol):
    """A protocol for determining storage space usage.

    This way, the storage of the whole can be computed from the size
    of its parts.

    """

    def size(self) -> int: ...

class IndexKeyType(enum.IntEnum):
    MATCH = 0
    LOOKUP = 1

class Index(Sizeable):
    def get_or(self, keys: list[tuple[IndexKeyType, Any]], thunk: Callable[[list[tuple[IndexKeyType, Any]]], Any]) -> Any:
        """Gets the value at `key` or calls `thunk` and stores it at `key`."""

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

class IndexFile(Index):
    def __init__(
            self,
            path: Optional[PathLike.Input],
            lock: PotentiallyReadersWriterLock = contextlib.nullcontext(),
    ) -> None:
        self._data = {
            IndexKeyType.LOOKUP: {},
            IndexKeyType.MATCH: (),
        }

    def get_or(self, keys: list[tuple[IndexKeyType, Any]], thunk: Callable[[list[tuple[IndexKeyType, Any]]], Any]) -> Any:
        ...
        # if len(keys) == 0:
        #     return thunk(keys)
        # else:
        #     key_type = keys[0][0]
        #     obj = self._data.get(key_type)
        #     for key_type, key in keys:
        #         if key_type == IndexKeyType.MATCH:
        #             if obj[0] == key:
        #                 obj[1]

        # if key in self.data:
        #     return self.data[key]
        # else:
        #     val = thunk(key)
        #     self.data[key] = val
        #     return val

Key = TypeVar("Key")
Val = TypeVar("Val")

class CoatCheck(Sizeable, Generic[Key, Val]):
    """Like a coat check at parties.

    - Guests hand over their coats, and the coat checker gives them an
      ID card.

    - At the end of the party, the guest hands over the ID card, and
      the coat checker gives them their coat.

    Unlike a dictionary/mapping/associative-array, the coat checker
    chooses the key; clients only supply the object. Thus, there is no
    `__setitem__`.

    """
    def check_in(self, val: Val) -> Key: ...
    def __getitem__(self, key: Key) -> Val: ...
    def __delitem__(self, key: Key) -> Val: ...

class KeyGen:
    """Generates unique keys (not cryptographically secure)."""
    def __init__(self, key_bits: int) -> None:
        self._key_bits = key_bits
        self._key_space = 2**self._key_bits
    def __iter__(self) -> KeyGen:
        return self
    def __next__(self) -> int:
        """Generates a new key."""
        return random.randint(0, 2**self._key_space-1)
    def probability_of_collision(self, keys: int) -> float:
        """Use to assert the probability of collision is acceptable."""
        try:
            import scipy
        except ImportError:
            raise ImportError("I require scipy to compute probability_of_collision")
        return 1 - cast(float, scipy.special.perm(self._key_space, keys, exact=False)) / (self._key_space ** keys)

class Pickler:
    def loads(self, buffer: bytes) -> Any: ...
    def dumps(self, val: Any) -> bytes: ...

T = TypeVar("T")

@attr.s
class Entry(Generic[T]):
    data_size: int
    compute_time: float
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
    def read_locked(self) -> Lock:
        return self.lock
    def write_locked(self) -> Lock:
        return self.lock

class IndexContainer:
    """Responsible for the telling an index when to persist."""
    def __init__(
            self,
            fine_grain_eviction: bool = False,
            fine_grain_persistence: bool = False,
    ) -> None:
        self._fine_grain_eviction = fine_grain_eviction
        self._fine_grain_persistence = fine_grain_persistence
        self._intro()
        atexit.register(self._outro)

    def _intro(self) -> None:
        if not self._fine_grain_persistence:
            self._load()

    def _lookup(self, key, thunk):
        if self._fine_grain_persistence:
            self._load()

        assert self._index_is_loaded
        present, entry = self._index.get(key)
        if present:
            # entry was present in the index
            # It may be None, but this is a "real" Val None.
            entry = cast(Val, entry)
        else:
            entry = thunk()
            self._index[key] = entry

        if self._fine_grain_eviction:
            self._evict()

        if self._fine_grain_persistence:
            self._store(merge=True)

        return entry

    def _outro(self) -> None:
        with self._thread_lock:
            if not self._fine_grain_persistence:
                self._store(merge=True)

    def _evict(self) -> None:
        while self._index.size() > self._limit:
            self._remove_one()

# https://github.com/micheles/decorator/blob/master/docs/documentation.md
# https://pypi.org/project/fasteners/

FuncParams = ParamSpec("FuncParams")
FuncReturn = TypeVar("FuncReturn")

def constant(val: Val) -> Callable[..., Val]:
    def fn(*args: Any, **kwargs: Any) -> Val:
        return val
    return fn

def memoize(
        **kwargs,
) -> Callable[[Callable[FuncParams, FuncReturn]], Callable[FuncParams, FuncReturn]]:
    def actual_memoize(func: Callable[FuncParams, FuncReturn], /) -> Callable[FuncParams, FuncReturn]:
        return Memoize[FuncParams, FuncReturn](func, **kwargs)
    return actual_memoize

@attr.s
class Memoize(Generic[FuncParams, FuncReturn]):
    def __attrs_post_init__(self):
        functools.update_wrapper(self, self._func)
        self._name = name if name is not None else f"{self._func.__module__}.{self._func.__qualname__}"
        self._logger = logging.getLogger("charmonium.cache").getChild(self.name)
        self._logger.setLevel(logging.DEBUG)
        self._handler = logging.StreamHandler(sys.stderr)
        self._handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
        if self._verbose:
            self.enable_logging()

    _func: Callable[FuncParams, FuncReturn]

    _index: Index

    _coat_check: CoatCheck

    _name: Optional[str] = None

    _verbose: bool = False

    _apply_coat_check: Callable[FuncParams, bool] = constant(True)

    _serializer: Serializer = pickle

    _extra_global_state: Callable[[], Any] = constant(None)
    def _global_state(self) -> Any:
        """
        - The global_state is the default global state () and
        `extra_global_state()`.

        """
        # TODO: other state about memoizaiton
        return (
            __version__,
            self._extra_global_state(),
        )

    _extra_func_state: Callable[Callable[FuncParams, FuncReturn], Any] = constant(None)
    def _func_state(self) -> Any:
        """
        - The func_state is the default func state (closed-over vars,
          the source, and `func.__version__()`) and
          `extra_func_state(func)`.

        """
        return (
            inspect.getclosurevars(self._func),
            inspect.getsource(self._func),
            self._func.__version__() if hasattr(self._func, "__version__") else None,
            self._extra_func_state(self._func)
        )

    _extra_args2key: Callable[FuncParams, FuncReturn] = constant(None)
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
            [
                val.__cache_key__() if hasattr(val, "__cache_key__") else val
                for arg_group in [enumerate(args), kwargs.items()]
                for key, val in arg_group
            ],
            self._extra_args2key(*args, **kwargs),
        )

    _extra_args2ver: Callable[FuncParams, FuncReturn] = constant(None)
    def _args2ver(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> Any:
        """Convert arguments to their version for caching.

        - See `args2key`. The version consists of the default and
          `extra_args2ver`. The default is `obj.__cache_ver__()` if it
          exists and None (no version) otherwise. Prefer to change
          `__cache_ver__` rather than `extra_args2ver`.

        """
        return (
            [
                val.__cache_ver__() if hasattr(val, "__cache_ver__") else None
                for arg_group in [enumerate(args), kwargs.items()]
                for key, val in arg_group
            ],
            self._extra_args2ver(*args, **kwargs)
        )

    def enable_logging(self) -> None:
        self._logger.addHandler(self._handler)

    def disable_logging(self) -> None:
        self._logger.removeHandler(self._handler)

    def __str__(self) -> str:
        store_type = type(self.obj_store).__name__
        return f"cached {self._name}"

    def _recompute(
            self,
            *args: FuncParams.args,
            **kwargs: FuncParams.kwargs,
    ) -> Entry[FuncReturn]:
        start = datetime.datetime.now()
        value = self._func(*args, **kwargs)
        stop = datetime.datetime.now()

        value_ser = self.serializer.dumps(value)
        data_size = len(value_ser)
        if self._apply_coat_check(*args, **kwargs):
            value_ser = self._coat_check.check_in(value_ser)
            data_size += len(value_ser)

        return Entry(
            data_size=data_size,
            compute_time=stop - start,
            value=value,
        )

    def __call__(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> FuncReturn:
        key = (
            self._global_state(),
            self._name,
            self._func_state(self._func),
            self._args2key(*args, **kwargs),
            self._args2ver(*args, **kwargs),
        )
        entry = self._index.get_or(key, self._recompute)
        entry.last_use = datetime.datetime.now()
        # TODO: have a last_used counter
        is_coat_checked, value_ser = entry.value

        if is_coat_checked:
            value_ser = self._coat_check[value_ser]
        value: FuncReturn = self._serializer.loads(value_ser)
        # TODO: figure out how to elide this `loads(dumps(...))`, if we did a recompute.

        return value

CACHE_LOC = Path(".cache/index")
