from __future__ import annotations

import atexit
import datetime
# import functools
# import heapq
import itertools
import importlib
import logging
import pickle
import sys
import threading
import warnings
from typing import Any, Callable, Final, Generic, Iterator, Mapping, Union, cast, Optional

import attr
import bitmath

from .func_version import func_version
from .persistent_hash import persistent_hash
from .index import Index, IndexKeyType
from .obj_store import DirObjStore, ObjStore
from .replacement_policies import Entry, ReplacementPolicy, REPLACEMENT_POLICIES
from .rw_lock import RWLock, FileRWLock, Lock
from .util import (
    Constant,
    FuncParams,
    FuncReturn,
    Future,
    GetAttr,
    KeyGen,
    Pickler,
)

# import cloudpickle


__version__ = "1.0.0"

BYTE_ORDER: Final[str] = "big"


def memoize(
    **kwargs: Any,
) -> Callable[[Callable[FuncParams, FuncReturn]], Memoized[FuncParams, FuncReturn]]:
    def actual_memoize(
        func: Callable[FuncParams, FuncReturn], /
    ) -> Memoized[FuncParams, FuncReturn]:
        # pyright doesn't know attrs __init__, hence type ignore
        return Memoized[FuncParams, FuncReturn](func, **kwargs)  # type: ignore

    # I believe pyright suffers from this fixed mypy bug: https://github.com/python/mypy/issues/1323
    # Therefore, I have to circumvent the type system.
    # However, somehow `cast` isn't sufficient.
    # Therefore, I need type ignore. I don't like it any more than you.
    # return cast(Memoized[FuncParams, FuncReturn], actual_memoize)
    return actual_memoize  # type: ignore


DEFAULT_LOCK_PATH = ".cache/.lock"
DEFAULT_OBJ_STORE_PATH = ".cache"
PICKLERS: Mapping[str, Callable[[], Pickler]] = {
    "pickle": lambda: pickle,
    "dill": lambda: importlib.import_module("dill"),
    "cloudpickle": lambda: importlib.import_module("cloudpickle"),
}

# pyright thinks attrs has ambiguous overload
@attr.define(init=False)  # type: ignore
class MemoizedGroup:
    """A MemoizedGroup holds the memoization for multiple functions."""

    _index: Index[Any, Entry]
    _obj_store: ObjStore
    _replacement_policy: ReplacementPolicy
    _key_gen: KeyGen
    _size: bitmath.Bitmath
    _pickler: Pickler
    _lock: RWLock
    _fine_grain_persistence: bool
    _fine_grain_eviction: bool
    _index_key: int
    _extra_system_state: Callable[[], Any]
    _use_count: Iterator[int]

    def __init__(
            self,
            obj_store: Optional[ObjStore] = None,
            replacement_policy: Union[str, ReplacementPolicy] = "dummy",
            size: Union[int, str, bitmath.Bitmath] = bitmath.MiB(1),
            pickler: Union[str, Pickler] = "pickle",
            lock: Optional[RWLock] = None,
            fine_grain_persistence: bool = False,
            fine_grain_eviction: bool = False,
            extra_system_state: Callable[[], Any] = Constant(None),
    ) -> None:
        """Test

        :param obj_store: The object store to use for return values.
        :param replacement_policy: See policies submodule for options. You can pass an object conforming to the ReplacementPolicy protocol or one of REPLACEMENT_POLICIES.
        :param size: The size as an int (in bytes), as a string (e.g. "3 MiB"), or as a `bitmath.Bitmath`_.
        :param pickler: A de/serialization to use on the index. You can pass an object conforming to the Pickler protocol or one of PICKLERS.
        :param lock: A ReadersWriterLock to achieve exclusion. If the lock is wrong but the obj_store is atomic, then the memoization is still *correct*, but it may not be able to borrow values that another machine computed. Defaults to a FileRWLock.
        :param fine_grain_persistence: De/serialize the index at every access. This is useful if you need to update the cache for multiple simultaneous processes, but it compromises performance in the single-process case.
        :param fine_grain_eviction: Maintain the cache's size through eviction at every access (rather than just the de/serialization points). This is useful if the caches size would not otherwise fit in memory, but it compromises performance if not needed.
        :param extra_system_state: A callable that returns "extra" system state. If the system state changes, the cache is dumped.

        .. _`bitmath.Bitmath`: https://pypi.org/project/bitmath/

        """
        self._index = Index[Any, Entry](
            (
                IndexKeyType.MATCH,  # system state
                IndexKeyType.LOOKUP,  # func name
                IndexKeyType.MATCH,  # func state
                IndexKeyType.LOOKUP,  # args key
                IndexKeyType.MATCH,  # args version
            )
        )
        self._obj_store = obj_store if obj_store is not None else DirObjStore(path=DEFAULT_OBJ_STORE_PATH)
        self._key_gen = KeyGen()
        self._replacement_policy = \
            REPLACEMENT_POLICIES[replacement_policy.lower()]() if isinstance(replacement_policy, str) else replacement_policy
        self._size = \
            size if isinstance(size, bitmath.Bitmath) else \
            bitmath.Byte(size) if isinstance(size, int) else \
            bitmath.parse_string(size)
        self._pickler = PICKLERS[pickler]() if isinstance(pickler, str) else pickler
        self._lock = lock if lock is not None else FileRWLock(DEFAULT_LOCK_PATH)
        self._fine_grain_persistence = fine_grain_persistence
        self._fine_grain_eviction = fine_grain_eviction
        self._extra_system_state = extra_system_state
        self._index_key = 0
        self._index_read()
        self._use_count = itertools.count()
        atexit.register(self._index_write)

    def _index_read(self) -> None:
        with self._lock.reader:
            if self._index_key in self._obj_store:
                # TODO: persist ReplacementPolicy state and friends
                other = cast(
                    Index[Any, Entry],
                    self._pickler.loads(self._obj_store[self._index_key]),
                )
                self._index.update(other)

    def _index_write(self) -> None:
        with self._lock.writer:
            if self._index_key in self._obj_store:
                other = cast(
                    Index[Any, Entry],
                    self._pickler.loads(self._obj_store[self._index_key]),
                )
                self._index.update(other)
            self._evict()
            self._obj_store[self._index_key] = self._pickler.dumps(self._index)

    def _system_state(self) -> Any:
        """Functions are deterministic with (global state, function-specific state, args key, args version).

        - The system_state contains:
          - Package version

        """
        return (__version__, self._extra_system_state())

    def _evict(self) -> None:
        # heap = list[tuple[float, tuple[Any, ...], Entry]]()
        total_size: bitmath.Bitmath = bitmath.Byte(0)

        for key, entry in self._index.items():
            # heapq.heappush(heap, (self._eval_func(entry), key, entry))
            total_size += entry.data_size

        while total_size > self._size:
            key, entry = self._replacement_policy.evict()
            if entry.obj_store:
                del self._obj_store[entry.value]
            total_size -= entry.data_size
            print("Evicting %s, %s" % (key[3][0], key[3][1]))
            del self._index[key]


DEFAULT_MEMOIZED_GROUP = Future[MemoizedGroup](fulfill_twice=True)
# TODO: Can I delay instantiating DirObjStore until I know that I am using it?
DEFAULT_MEMOIZED_GROUP.fulfill(MemoizedGroup())


# pyright thinks attrs has ambiguous overload
@attr.define(init=False)  # type: ignore
class Memoized(Generic[FuncParams, FuncReturn]):
    _func: Callable[FuncParams, FuncReturn]

    _group: Future[MemoizedGroup]

    _name: str

    _use_obj_store: bool

    # TODO: make this accept default_group_verbose = Sentinel()
    _verbose: bool

    _pickler: Optional[Pickler]

    _lock: Lock

    _logger: logging.Logger
    _handler: logging.Handler

    # TODO: persist time_cost, time_saved, date_began.
    time_cost: datetime.timedelta
    time_saved: datetime.timedelta

    _use_metadata_size: bool

    _extra_func_state: Callable[[Callable[FuncParams, FuncReturn]], Any] = cast(
        "Callable[[Callable[FuncParams, FuncReturn]], Any]", Constant(None)
    )
    _extra_args2key: Callable[FuncParams, Any] = Constant(None)
    _extra_args2ver: Callable[FuncParams, Any] = Constant(None)

    def __init__(
            self,
            func: Callable[FuncParams, FuncReturn],
            *,
            group: Future[MemoizedGroup] = DEFAULT_MEMOIZED_GROUP,
            name: Optional[str] = None,
            use_obj_store: bool = True,
            use_metadata_size: bool = False,
            verbose: bool = True,
            pickler: Union[Pickler, str, None] = None,
            extra_func_state: Callable[[Callable[FuncParams, FuncReturn]], Any] = Constant(None), # type: ignore
            extra_args2key: Callable[FuncParams, Any] = Constant(None),
            extra_args2ver: Callable[FuncParams, Any] = Constant(None),
    ) -> None:
        """

        :param use_metadata_size: whether to include the size of the metadata in the size threshold calculation for eviction.

        """

        self._func = func
        self._name = name if name is not None else f"{self._func.__module__}.{self._func.__qualname__}"
        self._group = group
        self._use_obj_store = use_obj_store
        self._use_metadata_size = use_metadata_size
        self._verbose = verbose
        self._pickler = PICKLERS[pickler]() if isinstance(pickler, str) else pickler
        self._lock = threading.RLock()
        self._extra_func_state = extra_func_state
        self._extra_args2key = extra_args2key
        self._extra_args2ver = extra_args2ver

        self._logger = logging.getLogger("charmonium.cache").getChild(self._name)
        self._logger.setLevel(logging.DEBUG)
        self._handler = logging.StreamHandler(sys.stderr)
        self._handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))

        if self._verbose:
            atexit.register(self.log_usage_report)
            self.enable_logging()

        # functools.update_wrapper(self, self._func)

        self.time_cost = datetime.timedelta()
        self.time_saved = datetime.timedelta()

    def log_usage_report(self) -> None:
        print(
            "Caching %s: cost %.1fs, saved %.1fs, net saved %.1fs" % (
                self._name,
                self.time_cost.total_seconds(),
                self.time_saved.total_seconds(),
                (self.time_saved - self.time_cost).total_seconds(),
            ),
            file=sys.stderr,
        )


    @property
    def pickler(self) -> Pickler:
        if self._pickler is None:
            return (
                # Group is a "friend class", hence pylint disable
                self._group._._pickler  # pylint: disable=protected-access
            )
        else:
            return self._pickler

    def _func_state(self) -> Any:
        """Returns function-specific state.

        See _system_state for the usage of function-specific state.

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
            persistent_hash(func_version(self._func)),
            GetAttr[str]()(
                self.pickler, "__name__", "", check_callable=False
            ),
            # Group is a "friend class", so pylint disable
            self._group._._obj_store,  # pylint: disable=protected-access
            GetAttr[Callable[[], Any]]()(self._func, "__version__", lambda: None)(),
            self._extra_func_state(self._func),
        )

    @staticmethod
    def _combine_args(
        *args: FuncParams.args, **kwargs: FuncParams.kwargs
    ) -> Mapping[str, Any]:
        return {
            **{str(key): val for key, val in enumerate(args)},
            **kwargs,
        }

    def _args2key(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> Any:
        """Convert arguments to their key for caching.

        - The cache uses the "args key" to mean "this is the same
          resource but possibly a different version." If the "args
          key" is the same, then "args version" assesses if the
          verison is new. For arguments which are not versioned
          resources, using that argument as the key and a constant as
          the version will work. This is the default."

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
            frozenset(
                {
                    key: GetAttr[Callable[[Any], Any]]()(
                        type(val), "__cache_key__", persistent_hash
                    )(val)
                    for key, val in self._combine_args(*args, **kwargs).items()
                }.items()
            ),
            self._extra_args2key(*args, **kwargs),
        )

    def _args2ver(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> Any:
        """Convert arguments to their version for caching.

        - See `args2key`. The version consists of the default and
          `extra_args2ver`. The default is `obj.__cache_ver__()` if it
          exists and None (no version) otherwise. Prefer to change
          `__cache_ver__` rather than `extra_args2ver`.

        """
        return (
            frozenset(
                {
                    type(key): GetAttr[Callable[[Any], Any]]()(
                        val, "__cache_ver__", Constant(None)
                    )(val)
                    for key, val in self._combine_args(*args, **kwargs).items()
                }.items()
            ),
            self._extra_args2ver(*args, **kwargs),
        )

    def enable_logging(self) -> None:
        self._logger.addHandler(self._handler)

    def disable_logging(self) -> None:
        self._logger.removeHandler(self._handler)

    def __str__(self) -> str:
        return f"memoized {self._name}"

    def _recompute(
        self, *args: FuncParams.args, **kwargs: FuncParams.kwargs
    ) -> tuple[Entry, FuncReturn]:
        start = datetime.datetime.now()
        value = self._func(*args, **kwargs)

        mid = datetime.datetime.now()

        if self._use_obj_store:
            value_ser = self.pickler.dumps(value)
            data_size = bitmath.Byte(len(value_ser))
            # Group is a "friend class", hence pylint disable
            stored_value = next(
                self._group._._key_gen  # pylint: disable=protected-access
            )
            self._group._._obj_store[  # pylint: disable=protected-access
                stored_value
            ] = value_ser
        else:
            stored_value = value
            data_size = bitmath.Byte(0)

        stop = datetime.datetime.now()

        # Returning value in addition to Entry elides the redundant `loads(dumps(...))` when obj_store is True.
        return (
            # pyright doesn't know attrs __init__, hence type ignore
            Entry(  # type: ignore
                data_size=data_size,
                recompute_time=stop - start,
                time_saved=mid - start,
                value=stored_value,
                obj_store=self._use_obj_store,
            ),
            value,
        )

    def __call__(
        self, *args: FuncParams.args, **kwargs: FuncParams.kwargs
    ) -> FuncReturn:
        with self._lock:
            start = datetime.datetime.now()

            key = (
                self._group._._system_state(),
                self._name,
                self._func_state(),
                self._args2key(*args, **kwargs),
                self._args2ver(*args, **kwargs),
            )

            if self._group._._fine_grain_persistence:
                self._group._._index_read()

            if key in self._group._._index:
                self._logger.debug("hit %s, %s", args, kwargs)
                entry = self._group._._index[key]
                if entry.obj_store:
                    value = cast(
                        FuncReturn,
                        self.pickler.loads(
                            self._group._._obj_store[cast(int, entry.value)]
                        ),
                    )
                else:
                    value = cast(FuncReturn, entry.value)
                self.time_saved += entry.time_saved
                self._group._._replacement_policy.access(key, entry)
            else:
                self._logger.debug("miss %s, %s", args, kwargs)
                entry, value = self._recompute(*args, **kwargs)
                if self._use_metadata_size:
                    entry.data_size += bitmath.Byte(len(self._group._._pickler.dumps(entry)))
                    entry.data_size += bitmath.Byte(len(self._group._._pickler.dumps(key)))
                self._group._._index[key] = entry
                self._group._._replacement_policy.add(key, entry)
                # TODO: Propagate possible deletions from index to obj_store.

            entry.last_use = datetime.datetime.now()
            # entry.last_use_count = next(self._group._._use_count)

            if self._group._._fine_grain_eviction:
                self._group._._evict()

            if self._group._._fine_grain_persistence:
                self._group._._index_write()

            stop = datetime.datetime.now()
            self.time_cost += stop - start

            if self.time_saved < self.time_cost and self.time_cost.total_seconds() > 5:
                warnings.warn(
                    f"Caching {self._func} cost {self.time_cost.total_seconds():.1f}s but only saved {self.time_saved.total_seconds():.1f}s",
                    UserWarning,
                )

            return value

    def would_hit(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> bool:
        key = (
            # Group is a friend class, hence type ignore
            self._group._._system_state(),  # pylint: disable=protected-access
            self._name,
            self._func_state(),
            self._args2key(*args, **kwargs),
            self._args2ver(*args, **kwargs),
        )

        if self._group._._fine_grain_persistence:  # pylint: disable=protected-access
            self._group._._index_read() # pylint: disable=protected-access

        print(key)

        return key in self._group._._index # pylint: disable=protected-access
