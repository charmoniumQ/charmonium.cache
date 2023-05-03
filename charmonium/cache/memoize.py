from __future__ import annotations

import atexit
import contextlib
import copy
import dataclasses
import datetime
import json
import logging
import os
import pickle
import random
import sys
import threading
import warnings
from typing import (
    Any,
    Callable,
    DefaultDict,
    Generic,
    Generator,
    Mapping,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)

import bitmath  # type: ignore
from charmonium.freeze import freeze, Config as FreezeConfig, global_config

from .index import Index, IndexKeyType
from .obj_store import DirObjStore, ObjStore
from .pickler import Pickler
from .replacement_policies import REPLACEMENT_POLICIES, Entry, ReplacementPolicy
from .rw_lock import FileRWLock, Lock, RWLock
from .util import (
    Constant,
    FuncParams,
    FuncReturn,
    Future,
    GetAttr,
    identity,
    none_tuple,
)

BYTE_ORDER: str = "big"

__version__ = "1.4.1"

DEFAULT_FREEZE_CONFIG = copy.deepcopy(global_config)
DEFAULT_FREEZE_CONFIG.use_hash = True
DEFAULT_FREEZE_CONFIG.ignore_classes.update(
    {
        ("charmonium.cache.memoize", "Memoized"),
        ("charmonium.cache.memoize", "MemoizedGroup"),
    }
)
DEFAULT_FREEZE_CONFIG.ignore_attributes.update(
    {
        ("charmonium.cache.memoize", "Memoized", "group"),
        ("charmonium.cache.memoize", "Memoized", "_use_obj_store"),
        ("charmonium.cache.memoize", "Memoized", "_use_metadata_size"),
        ("charmonium.cache.memoize", "Memoized", "_my_pickler"),
        ("charmonium.cache.memoize", "Memoized", "_extra_func_state"),
    }
)


def memoize(
    **kwargs: Any,
) -> Callable[[Callable[FuncParams, FuncReturn]], Memoized[FuncParams, FuncReturn]]:
    """See :py:class:`charmonium.cache.Memoized`."""
    def actual_memoize(
        func: Callable[FuncParams, FuncReturn]
    ) -> Memoized[FuncParams, FuncReturn]:
        return Memoized[FuncParams, FuncReturn](func, **kwargs)
    return actual_memoize


DEFAULT_LOCK_PATH = ".cache/.lock"
DEFAULT_OBJ_STORE_PATH = ".cache"


ops_logger = logging.getLogger("charmonium.cache.ops")
# all operations are logged as DEBUG
perf_logger = logging.getLogger("charmonium.cache.perf")
# all perf data is logged as DEBUG

perf_logger_file = os.environ.get("CHARMONIUM_CACHE_PERF_LOG")
if perf_logger_file:
    perf_logger.setLevel(logging.DEBUG)
    perf_logger.addHandler(logging.FileHandler(perf_logger_file))
    perf_logger.propagate = False


@contextlib.contextmanager
def perf_ctx(event: str, call_id: int) -> Generator[None, None, None]:
    if perf_logger.isEnabledFor(logging.DEBUG):
        start = datetime.datetime.now()
    yield
    if perf_logger.isEnabledFor(logging.DEBUG):
        perf_logger.debug(
            json.dumps(
                {
                    "event": event,
                    "duration": (datetime.datetime.now() - start).total_seconds(),
                    "call_id": call_id,
                }
            )
        )


@dataclasses.dataclass
class MemoizedGroup:
    """A MemoizedGroup holds the memoization for multiple functions."""

    # pylint: disable=too-many-instance-attributes

    _index: Index[Any, Entry]
    _obj_store: ObjStore
    _replacement_policy: ReplacementPolicy
    _size: bitmath.Bitmath
    _index_lock: RWLock
    _memory_lock: Lock
    _fine_grain_persistence: bool
    _fine_grain_eviction: bool
    _index_key: int
    _extra_system_state: Callable[[], Any]
    _version: int
    _pickler: Pickler
    time_cost: dict[str, datetime.timedelta]
    time_saved: dict[str, datetime.timedelta]
    temporary: bool

    def __getstate__(self) -> Any:
        return {
            slot: getattr(self, slot)
            for slot in self.__dict__
            if slot not in {"__weakref__", "_index", "_memory_lock", "_version"}
        }

    def __setstate__(self, state: Mapping[str, Any]) -> Any:
        for attr_name, attr_val in state.items():
            setattr(self, attr_name, attr_val)
        self._index = Index[Any, Entry](
            (
                IndexKeyType.MATCH,  # system state
                IndexKeyType.LOOKUP,  # func name
                IndexKeyType.MATCH,  # func state
                IndexKeyType.LOOKUP,  # args key
                IndexKeyType.MATCH,  # args version
            ),
            self._deleter,
        )
        self._version = 0
        self._memory_lock = threading.RLock()
        self._index_read(0)

    def __init__(
        self,
        *,
        obj_store: Optional[ObjStore] = None,
        replacement_policy: Union[str, ReplacementPolicy] = "gdsize",
        size: Union[int, str, bitmath.Bitmath] = bitmath.KiB(100),
        pickler: Pickler = pickle,
        lock: Optional[RWLock] = None,
        fine_grain_persistence: bool = False,
        fine_grain_eviction: bool = False,
        extra_system_state: Callable[[], Any] = Constant(None),
        freeze_config: FreezeConfig = DEFAULT_FREEZE_CONFIG,
        temporary: bool = False,
    ) -> None:
        """Construct a memoized group. Use with :py:function:Memoized.

        :param obj_store: The object store to use for return values.
        :param replacement_policy: See policies submodule for options. You can pass an object conforming to the ReplacementPolicy protocol or one of REPLACEMENT_POLICIES.
        :param size: The size as an int (in bytes), as a string (e.g. "3 MiB"), or as a `bitmath.Bitmath`_.
        :param pickler: A de/serialization to use on the index, conforming to the Pickler protocol.
        :param lock: A ReadersWriterLock to achieve exclusion. If the lock is wrong but the obj_store is atomic, then the memoization is still *correct*, but it may not be able to borrow values that another machine computed. Defaults to a FileRWLock.
        :param fine_grain_persistence: De/serialize the index at every access. This is useful if you need to update the cache for multiple simultaneous processes, but it compromises performance in the single-process case.
        :param fine_grain_eviction: Maintain the cache's size through eviction at every access (rather than just the de/serialization points). This is useful if the caches size would not otherwise fit in memory, but it compromises performance if not needed.
        :param extra_system_state: A callable that returns "extra" system state. If the system state changes, the cache is dumped.
        :param freeze_config: A charmonium.freeze.Config object. This config determines how objects and functions get hashed.
        :param temporary: Whether the cache should be cleared at the end of the process; This is useful for tests.

        .. _`bitmath.Bitmath`: https://pypi.org/project/bitmath/

        """
        self._obj_store = (
            obj_store
            if obj_store is not None
            else DirObjStore(path=DEFAULT_OBJ_STORE_PATH)
        )
        self._replacement_policy = (
            REPLACEMENT_POLICIES[replacement_policy.lower()]()
            if isinstance(replacement_policy, str)
            else replacement_policy
        )
        self._size = (
            size
            if isinstance(size, bitmath.Bitmath)
            else bitmath.Byte(size)
            if isinstance(size, int)
            else bitmath.parse_string(size)
        )
        self._pickler = pickler
        self._index_lock = lock if lock is not None else FileRWLock(DEFAULT_LOCK_PATH)
        self._fine_grain_persistence = fine_grain_persistence
        self._fine_grain_eviction = fine_grain_eviction
        self._extra_system_state = extra_system_state
        self._index_key = 0
        self._freeze_config = freeze_config
        assert self._freeze_config.hasher is not None, "Hashing must be enabled in freeze_config"
        self.time_cost = DefaultDict[str, datetime.timedelta](datetime.timedelta)
        self.time_saved = DefaultDict[str, datetime.timedelta](datetime.timedelta)
        self.temporary = temporary
        self.__setstate__({})
        if self.temporary:
            atexit.register(self._obj_store.clear)
            # atexit handlers are run in the opposite order they are registered.
        atexit.register(self._index_write, 0)
        # TODO: atexit log report

    def _deleter(self, item: tuple[Any, Entry]) -> None:
        with self._memory_lock:
            key, entry = item
            if entry.obj_store:
                obj_key = cast(int, freeze(key, self._freeze_config))
                del self._obj_store[obj_key]
            else:
                obj_key = None
            self._replacement_policy.invalidate(key, entry)
        if ops_logger.isEnabledFor(logging.DEBUG):
            ops_logger.debug(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "tid": threading.get_native_id(),
                        "event": "cascading_delete",
                        "key": key,
                        "obj_key": obj_key,
                    }
                )
            )

    def _index_read(self, call_id: int) -> None:
        with self._memory_lock, self._index_lock.reader:
            self._index_read_nolock(call_id)

    def _index_read_nolock(self, call_id: int) -> None:
        current_version = self._version
        with perf_ctx("index_read", call_id):
            if self._index_key in self._obj_store:
                other_version, other_index, other_rp, other_tc, other_ts = cast(
                    Tuple[
                        int,
                        Index[Any, Entry],
                        ReplacementPolicy,
                        DefaultDict[str, datetime.timedelta],
                        DefaultDict[str, datetime.timedelta],
                    ],
                    self._pickler.loads(self._obj_store[self._index_key]),
                )
                if other_version > current_version:
                    self._version = other_version
                    self._index.update(other_index)
                    self._replacement_policy.update(other_rp)
                    self.time_cost = other_tc
                    self.time_saved = other_ts
        if ops_logger.isEnabledFor(logging.DEBUG):
            ops_logger.debug(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "tid": threading.get_native_id(),
                        "event": "index_read",
                        "old_version": current_version,
                        "self._version": self._version,
                        "call_id": call_id,
                    }
                )
            )

    def _index_write(self, call_id: int) -> None:
        with perf_ctx("index_write", call_id), self._memory_lock, self._index_lock.writer:
            self._index_read_nolock(call_id)
            self._evict()
            self._version += 1
            self._obj_store[self._index_key] = self._pickler.dumps(
                (
                    self._version,
                    self._index,
                    self._replacement_policy,
                    self.time_cost,
                    self.time_saved,
                )
            )
        if ops_logger.isEnabledFor(logging.DEBUG):
            ops_logger.debug(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "tid": threading.get_native_id(),
                        "event": "index_write",
                        "self._version": self._version,
                        "call_id": call_id,
                    }
                )
            )

    def _system_state(self) -> Any:
        """Functions are deterministic with (global state, function-specific state, args key, args version).

        - The system_state contains:
          - Package version

        """
        with self._memory_lock:
            return (__version__,) + none_tuple(self._extra_system_state())

    def _evict(self) -> None:
        with self._memory_lock:
            total_size: bitmath.Bitmath = bitmath.Byte(0)

            for key, entry in self._index.items():
                # heapq.heappush(heap, (self._eval_func(entry), key, entry))
                total_size += entry.data_size

            while total_size > self._size:
                key, entry = self._replacement_policy.evict()
                if entry.obj_store:
                    obj_key = cast(int, freeze(key, self._freeze_config))
                    assert (
                        obj_key in self._obj_store
                    ), "Replacement policy tried to evict something that wasn't there"
                    del self._obj_store[obj_key]
                else:
                    obj_key = None
                total_size -= entry.data_size
                if ops_logger.isEnabledFor(logging.DEBUG):
                    ops_logger.debug(
                        json.dumps(
                            {
                                "pid": os.getpid(),
                                "tid": threading.get_native_id(),
                                "event": "evict",
                                "key": key,
                                "obj_key": obj_key,
                                "entry.data_size": entry.data_size.bytes,
                                "new_total_size": (total_size - entry.data_size).bytes,
                            }
                        )
                    )
                del self._index[key]

    def remove_orphans(self) -> None:
        """Remove data in the objstore that are not referenced by the index.

        Orphans can accumulate if there are multiple processes. They
        might generate orphans if they crash or if there is a bug in
        my code (yikes!). If you notice accumulation of orphans, I
        recommend calling this function once or once-per-pipeline to
        clean them up.

        However, this can compromise performance if you do it while
        peer processes are active. They may have a slightly different
        index-state, and you might remove something they wanted to
        keep. I recommend calling this before you fork off processes.

        """
        with self._memory_lock:
            found_obj_keys = {
                entry.value for _, entry in self._index.items() if entry.obj_store
            }
            for obj_key in self._obj_store:
                if obj_key not in found_obj_keys:
                    if ops_logger.isEnabledFor(logging.DEBUG):
                        ops_logger.debug(
                            json.dumps(
                                {
                                    "pid": os.getpid(),
                                    "tid": threading.get_native_id(),
                                    "event": "remove_orphan",
                                    "obj_key": obj_key,
                                }
                            )
                        )
                    del self._obj_store[obj_key]


DEFAULT_MEMOIZED_GROUP = Future[MemoizedGroup].create(
    cast(Callable[[], MemoizedGroup], MemoizedGroup)
)


class CacheThrashingWarning(UserWarning):
    pass


@dataclasses.dataclass
class Memoized(Generic[FuncParams, FuncReturn]):
    # pylint: disable=too-many-instance-attributes
    func: Callable[FuncParams, FuncReturn]

    group: MemoizedGroup

    name: str

    _use_obj_store: bool

    _use_metadata_size: bool

    _my_pickler: Optional[Pickler]

    _extra_func_state: Callable[[Callable[FuncParams, FuncReturn]], Any]

    def __init__(
        self,
        func: Callable[FuncParams, FuncReturn],
        *,
        group: MemoizedGroup = DEFAULT_MEMOIZED_GROUP,
        name: Optional[str] = None,
        use_obj_store: bool = True,
        use_metadata_size: bool = False,
        pickler: Optional[Pickler] = None,
        extra_func_state: Callable[[Callable[FuncParams, FuncReturn]], Any] = Constant(None),  # type: ignore
    ) -> None:
        """Construct a memozied function

        :param group: see :py:class:`charmonium.cache.MemoizedGroup`.
        :param name: A key-to-lookup distinguishing this funciton from others. Defaults to the Python module and name.
        :param extra_func_state: An extra state function. The return-value is a key-to-match after the function name.
        :param use_obj_store: whether the objects should be put behind object store, a layer of indirection.
        :param use_metadata_size: whether to include the size of the metadata in the size threshold calculation for eviction.
        :param pickler: A custom pickler to use with the index. Pickle types must include tuples of picklable types, hashable types, and the arguments (``__cache_key__`` and ``__cache_var__``, if defined).
        """

        # TODO: use functools.wraps()
        self.func = func
        self.name = (
            name
            if name is not None
            else f"{self.func.__module__}.{self.func.__qualname__}"
        )
        self.__qualname__ = self.func.__qualname__
        self.group = group
        self._use_obj_store = use_obj_store
        self._use_metadata_size = use_metadata_size
        self._my_pickler = pickler
        self._extra_func_state = extra_func_state

        if not self._use_obj_store and not self._use_metadata_size:
            warnings.warn(
                "You are not using the object store, so function return-values get "
                "serialized into the metadata, but you are also not using "
                "the metadata size for eviction. This will likely lead to "
                "an unbounded cache. If you care about the boundedness, set "
                "either `use_obj_store` or `use_metadata_size`. ",
                UserWarning,
            )

        # functools.update_wrapper(self, self.func)

    def log_usage_report(self) -> None:
        with self.group._memory_lock:  # pylint: disable=protected-access
            tc = self.group.time_cost[self.name]
            ts = self.group.time_saved[self.name]
        print(
            f"Caching {self.name}: "
            f"cost {tc.total_seconds():.1f}s, "
            f"saved {ts.total_seconds():.1f}s, "
            f"net saved {(ts - tc).total_seconds():.1f}s",
            file=sys.stderr,
        )

    @property
    def _pickler(self) -> Pickler:
        if self._my_pickler is None:
            return (
                # Group is a "friend class", hence pylint disable
                self.group._pickler  # pylint: disable=protected-access
            )
        else:
            return self._my_pickler

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
            self.func,
            GetAttr[Callable[[], Any]]()(
                self.func, "__version__", lambda: None, check_callable=True
            )(),
        ) + none_tuple(self._extra_func_state(self.func))

    @staticmethod
    def _combine_args(
        *args: FuncParams.args, **kwargs: FuncParams.kwargs
    ) -> Mapping[Any, Any]:
        return {
            **dict(enumerate(args)),
            **kwargs,
        }

    def _args2key(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> Any:
        return {
            key: GetAttr[Callable[[Any], Any]]()(
                type(val), "__cache_key__", identity, check_callable=True
            )(val)
            for key, val in self._combine_args(*args, **kwargs).items()
        }

    def _args2ver(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> Any:
        return {
            key: GetAttr[Callable[[Any], Any]]()(
                type(val), "__cache_ver__", Constant(()), check_callable=True
            )(val)
            for key, val in self._combine_args(*args, **kwargs).items()
        }

    def __str__(self) -> str:
        return f"memoized {self.name}"

    def _recompute(
        self,
        call_id: int,
        obj_key: int,
        *args: FuncParams.args,
        **kwargs: FuncParams.kwargs,
    ) -> tuple[Entry, FuncReturn]:

        start = datetime.datetime.now()
        value = self.func(*args, **kwargs)

        mid = datetime.datetime.now()

        if self._use_obj_store:
            stored_value = None
            value_ser = self._pickler.dumps(value)
            data_size = bitmath.Byte(len(value_ser))
            # Group is a "friend class", hence pylint disable

            with perf_ctx("obj_store", call_id):
                self.group._obj_store[  # pylint: disable=protected-access
                    obj_key
                ] = value_ser
        else:
            stored_value = value
            data_size = bitmath.Byte(0)

        stop = datetime.datetime.now()

        # TODO: cache stdout?

        if perf_logger.isEnabledFor(logging.DEBUG):
            perf_logger.debug(
                json.dumps(
                    {
                        "event": "serialize",
                        "call_id": call_id,
                        "duration": (stop - mid).total_seconds(),
                    }
                )
            )
            perf_logger.debug(
                json.dumps(
                    {
                        "event": "inner_function",
                        "call_id": call_id,
                        "duration": (mid - start).total_seconds(),
                    }
                )
            )

        return (
            Entry(
                data_size=data_size,
                function_time=mid - start,
                serialization_time=stop - mid,
                value=stored_value,
                obj_store=self._use_obj_store,
            ),
            value,
            # Returning value in addition to Entry elides the redundant `loads(dumps(...))` when obj_store is True.
        )

    def __getfrozenstate__(self) -> Callable[..., Any]:
        return self.func

    def _try_unpickle(self, value_ser: bytes, call_id: int) -> Tuple[bool, Optional[FuncReturn]]:
        with perf_ctx("deserialize", call_id):
            try:
                value = cast(FuncReturn, self._pickler.loads(value_ser))
            except (EOFError, pickle.UnpicklingError):
                return False, None
            else:
                return True, value

    def __call__(
        self, *args: FuncParams.args, **kwargs: FuncParams.kwargs
    ) -> FuncReturn:
        call_start = datetime.datetime.now()
        call_id = random.randint(0, 2**64 - 1)

        key, entry, obj_key, value_ser = self._would_hit(call_id, *args, **kwargs)

        hit, value = False, None
        if entry is not None:
            if entry.obj_store:
                if value_ser is not None:
                    hit, value = self._try_unpickle(value_ser, call_id)
            else:
                hit, value = True, cast(FuncReturn, entry.value)

        if ops_logger.isEnabledFor(logging.DEBUG):
            ops_logger.debug(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "tid": threading.get_native_id(),
                        "event": "hit" if hit else "miss",
                        "call_id": call_id,
                        "name": self.name,
                        "key": key,
                        "obj_key": obj_key,
                        # "args_kwargs": ellipsize(str(args) + " " + str(kwargs), 60),
                    }
                )
            )

        if not hit:
            # Do the recompute
            entry, value = self._recompute(call_id, obj_key, *args, **kwargs)
        else:
            # These assertions satisfy the type-checker.
            # Also probably a good idea.
            assert entry is not None
            assert value is not None

        with self.group._memory_lock:
            if hit:
                # Update time_saved
                self.group.time_saved[self.name] += entry.function_time
                self.group._replacement_policy.access(key, entry)
            else:
                # Do the store
                if self._use_metadata_size:
                    if not self._use_obj_store:
                        entry.data_size += bitmath.Byte(
                            len(self.group._pickler.dumps(entry))
                        )
                    entry.data_size += bitmath.Byte(len(self.group._pickler.dumps(key)))
                self.group._index[key] = entry
                self.group._replacement_policy.add(key, entry)

            # Update time_cost
            if self.group._fine_grain_eviction:
                self.group._evict()

            if self.group._fine_grain_persistence:
                self.group._index_write(call_id)

            call_stop = datetime.datetime.now()
            time_cost_inevitable = (
                datetime.timedelta(seconds=0) if hit else entry.function_time
            )
            # time-cost is the overhead of caching, so  it should exclud ethe overhead of the function.
            self.group.time_cost[self.name] += (
                call_stop - call_start - time_cost_inevitable
            )

            tc = self.group.time_cost[self.name]
            ts = self.group.time_saved[self.name]

        if perf_logger.isEnabledFor(logging.DEBUG):
            perf_logger.debug(
                json.dumps(
                    {
                        "name": self.name,
                        "event": "outer_function",
                        "call_id": call_id,
                        "hit": hit,
                        "duration": (call_stop - call_start).total_seconds(),
                    }
                )
            )

        if ts < tc and tc.total_seconds() > 5:
            warnings.warn(
                f"Caching {self.func.__qualname__} cost {tc.total_seconds():.1f}s but only saved {ts.total_seconds():.1f}s",
                CacheThrashingWarning,
            )

        return value

    def call_if_cached(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> tuple[bool, Optional[FuncReturn]]:
        """If function(input) hits in the cache, return (True, result), otherwise (False, None).

        This function does not mark the cache entry as accessed, count
        towards time saved, or write the index, because there is no
        analagous operation (call_if_cached) for an uncached function.

        That makes it fast.

        """

        call_start = datetime.datetime.now()
        call_id = random.randint(0, 2**64 - 1)
        key, entry, obj_key, value_ser = self._would_hit(call_id, *args, **kwargs)
        hit, value = False, None
        if entry is not None:
            if entry.obj_store:
                if value_ser is not None:
                    hit, value = self._try_unpickle(value_ser, call_id)
            else:
                hit, value = True, cast(FuncReturn, entry.value)
        call_stop = datetime.datetime.now()
        if perf_logger.isEnabledFor(logging.DEBUG):
            perf_logger.debug(
                json.dumps(
                    {
                        "name": self.name,
                        "event": "outer_function",
                        "call_id": call_id,
                        "hit": hit,
                        "duration": (call_stop - call_start).total_seconds(),
                    }
                )
            )
        return hit, value

    def would_hit(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> bool:
        call_id = random.randint(0, 2**64 - 1)
        key, entry, obj_key, value_ser = self._would_hit(call_id, *args, **kwargs)
        would_hit = entry is not None and (not entry.obj_store or value_ser is not None)
        if ops_logger.isEnabledFor(logging.DEBUG):
            ops_logger.debug(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "tid": threading.get_native_id(),
                        "event": "hit" if would_hit else "miss",
                        "call_id": call_id,
                        "name": self.name,
                        "key": key,
                        "obj_key": obj_key,
                        # "args_kwargs": ellipsize(str(args) + " " + str(kwargs), 60),
                    }
                )
            )
        return would_hit

    def _would_hit(
        self, call_id: int, *args: FuncParams.args, **kwargs: FuncParams.kwargs
    ) -> Tuple[Tuple[Any, ...], Optional[Entry], int, Optional[bytes]]:
        # pylint: disable=protected-access

        with perf_ctx("hash", call_id):
            # Note that the system state and name or so small already, it isn't worth hashing them.
            # They are also used by other Memoized functions in the same MemoizedGroup.
            # We will only hash the potentially large key items that are used exclusively by this Memoized function.
            key = (
                # Group is a friend class, hence type ignore
                freeze(
                    self.group._system_state(), self.group._freeze_config
                ),  # pylint: disable=protected-access
                freeze(self.name, self.group._freeze_config),
                freeze(self._func_state(), self.group._freeze_config),
                freeze(self._args2key(*args, **kwargs), self.group._freeze_config),
                freeze(self._args2ver(*args, **kwargs), self.group._freeze_config),
            )
            obj_key = cast(int, freeze(key, self.group._freeze_config))
        with self.group._memory_lock:
            if self.group._fine_grain_persistence:
                self.group._index_read(call_id)
            return (
                key,
                self.group._index.get(key, None),
                obj_key,
                self.group._obj_store.get(obj_key, None) if self._use_obj_store else None,
            )

    def __get__(self, instance: Any, instancetype: Type[Any]) -> BoundMemoized[FuncParams, FuncReturn]:
        """Implement the descriptor protocol to make decorating instance
        method possible.

        """
        # See https://stackoverflow.com/a/5470017/1078199
        # If we are accessed from the descriptor protocol, we must be a method attached to an object.
        # Bind self.
        return BoundMemoized[FuncParams, FuncReturn](self, instance)


class BoundMemoized(Generic[FuncParams, FuncReturn]):
    def __init__(
        self, memoized: Memoized[FuncParams, FuncReturn], instance: Any
    ) -> None:
        self.memoized = memoized
        self.instance = instance

    def __call__(
        self, *args: FuncParams.args, **kwargs: FuncParams.kwargs
    ) -> FuncReturn:
        return self.memoized(self.instance, *args, **kwargs)

    def __getattr__(self, attribute: str) -> Any:
        return getattr(self.memoized, attribute)
