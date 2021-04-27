from __future__ import annotations

import atexit
import datetime
# import functools
# import heapq
import logging
import pickle
import sys
import threading
import warnings
from typing import Any, Callable, Final, Generic, Mapping, Optional, Union, cast

import attr
import bitmath

from .determ_hash import determ_hash, hashable
from .index import Index, IndexKeyType
from .obj_store import DirObjStore, ObjStore
from .pickler import Pickler
from .replacement_policies import REPLACEMENT_POLICIES, Entry, ReplacementPolicy
from .rw_lock import FileRWLock, Lock, RWLock
from .util import Constant, FuncParams, FuncReturn, Future, GetAttr, KeyGen, identity, none_tuple

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
    _version: int

    def __init__(
            self,
            *,
            obj_store: Optional[ObjStore] = None,
            replacement_policy: Union[str, ReplacementPolicy] = "dummy",
            size: Union[int, str, bitmath.Bitmath] = bitmath.MiB(1),
            pickler: Pickler = pickle,
            lock: Optional[RWLock] = None,
            fine_grain_persistence: bool = False,
            fine_grain_eviction: bool = False,
            extra_system_state: Callable[[], Any] = Constant(None),
    ) -> None:
        """Test

        :param obj_store: The object store to use for return values.
        :param replacement_policy: See policies submodule for options. You can pass an object conforming to the ReplacementPolicy protocol or one of REPLACEMENT_POLICIES.
        :param size: The size as an int (in bytes), as a string (e.g. "3 MiB"), or as a `bitmath.Bitmath`_.
        :param pickler: A de/serialization to use on the index, conforming to the Pickler protocol.
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
            ),
            self._deleter,
        )
        self._obj_store = obj_store if obj_store is not None else DirObjStore(path=DEFAULT_OBJ_STORE_PATH)
        self._key_gen = KeyGen()
        self._replacement_policy = \
            REPLACEMENT_POLICIES[replacement_policy.lower()]() if isinstance(replacement_policy, str) else replacement_policy
        self._size = \
            size if isinstance(size, bitmath.Bitmath) else \
            bitmath.Byte(size) if isinstance(size, int) else \
            bitmath.parse_string(size)
        self._pickler = pickler
        self._lock = lock if lock is not None else FileRWLock(DEFAULT_LOCK_PATH)
        self._fine_grain_persistence = fine_grain_persistence
        self._fine_grain_eviction = fine_grain_eviction
        self._extra_system_state = extra_system_state
        self._index_key = 0
        self._index_read()
        self._version = 0
        atexit.register(self._index_write)

    def _deleter(self, item: tuple[Any, Entry]) -> None:
        key, entry = item
        if entry.obj_store:
            del self._obj_store[entry.value]
        self._replacement_policy.invalidate(key, entry)

    def _index_read(self) -> None:
        with self._lock.reader:
            if self._index_key in self._obj_store:
                # TODO: persist ReplacementPolicy state and friends
                other_version, other_index, other_rp = cast(
                    tuple[Index[Any, Entry], ReplacementPolicy],
                    self._pickler.loads(self._obj_store[self._index_key]),
                )
                if other_version > self._version:
                    self._version = other_version
                    self._index.update(other_index)
                    self._replacement_policy.update(other_rp)

    def _index_write(self) -> None:
        with self._lock.writer:
            if self._index_key in self._obj_store:
                other_version, other_index, other_rp = cast(
                    tuple[Index[Any, Entry], ReplacementPolicy],
                    self._pickler.loads(self._obj_store[self._index_key]),
                )
                if other_version > self._version:
                    self._version = other_version
                    self._index.update(other_index)
                    self._replacement_policy.update(other_rp)
            self._evict()
            self._version += 1
            self._obj_store[self._index_key] = self._pickler.dumps((self._version, self._index, self._replacement_policy))

    def _system_state(self) -> Any:
        """Functions are deterministic with (global state, function-specific state, args key, args version).

        - The system_state contains:
          - Package version

        """
        return (__version__,) + none_tuple(self._extra_system_state())

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
            del self._index[key]


DEFAULT_MEMOIZED_GROUP = Future[MemoizedGroup].create(cast(Callable[[], MemoizedGroup], MemoizedGroup))


# pyright thinks attrs has ambiguous overload
@attr.define(init=False)  # type: ignore
class Memoized(Generic[FuncParams, FuncReturn]):
    _func: Callable[FuncParams, FuncReturn]

    group: MemoizedGroup

    _name: str

    _use_obj_store: bool

    _use_metadata_size: bool

    _lossy_compression: bool

    # TODO: make this accept default_group_verbose = Sentinel()
    _verbose: bool

    _pickler: Optional[Pickler]

    _extra_func_state: Callable[[Callable[FuncParams, FuncReturn]], Any]
    _extra_args2key: Callable[FuncParams, Any]
    _extra_args2ver: Callable[FuncParams, Any]

    _lock: Lock

    _logger: logging.Logger
    _handler: logging.Handler

    # TODO: persist time_cost, time_saved, date_began.
    time_cost: datetime.timedelta
    time_saved: datetime.timedelta

    def __init__(
            self,
            func: Callable[FuncParams, FuncReturn],
            *,
            group: MemoizedGroup = DEFAULT_MEMOIZED_GROUP,
            name: Optional[str] = None,
            use_obj_store: bool = True,
            use_metadata_size: bool = False,
            lossy_compression: bool = True,
            verbose: bool = True,
            pickler: Optional[Pickler] = None,
            extra_func_state: Callable[[Callable[FuncParams, FuncReturn]], Any] = Constant(None), # type: ignore
            extra_args2key: Callable[FuncParams, Any] = Constant(None),
            extra_args2ver: Callable[FuncParams, Any] = Constant(None),
    ) -> None:
        """

Storing the whole argument is usually overkill; just storing a hash will do (the default
behavior). Python's |hash|_ will return different values across different runs, so I use
|determ_hash|_.  If for some reason you *do* want to keep the whole object, set ``memoize(...,
use_hash=False)``.

.. |hash| replace:: ``hash``
.. _`hash`: https://docs.python.org/3/library/functions.html?highlight=hash#hash

.. |determ_hash| replace:: ``determ_hash``
.. _`determ_hash`: http://example.com

.. TODO: API URLs

By default, the index entry just holds an object key and the object store maps that to the actual
returned object. This level of indirection means that the index is small and can be loaded quickly
even if the returned objects are big. If the returned objects are small, you can omit the
indirection by setting ``memoize(..., use_obj_store=False)``.

By default, only the object size (not index metadata) is counted towards the size of retaining an
object, but if the object is stored in the index, the object size will be zero.  then the
metadata. Set ``memoize(..., use_metadata_size)`` to include metadata in the size calculation. This
is a bit slower, so it is not the default.

By default, the cache is only culled to the desired size just before serialization. To cull the
cache after every store, set ``memoize(..., fine_grain_eviction=True)``. This is useful if the cache
would run out of memory without an eviction.

Be aware of ``memoize(..., verbose=True|False)``. If verbose is enabled, the cache will emit a
report at process-exit saying how much time was saved. This is useful to determine if caching is
"worth it."

        :param use_metadata_size: whether to include the size of the metadata in the size threshold calculation for eviction.
        :param lossy_compression: whether to use a hash of the arguments or the actual arguments. A hash will be faster and smaller, but the actual values are more useful for debugging.

        """

        self._func = func
        self._name = name if name is not None else f"{self._func.__module__}.{self._func.__qualname__}"
        self.group = group
        self._use_obj_store = use_obj_store
        self._use_metadata_size = use_metadata_size
        self._lossy_compression = lossy_compression
        self._verbose = verbose
        self._pickler = pickler
        self._lock = threading.RLock()
        self._extra_func_state = extra_func_state
        self._extra_args2key = extra_args2key
        self._extra_args2ver = extra_args2ver

        self._logger = logging.getLogger("charmonium.cache").getChild(self._name)
        self._logger.setLevel(logging.DEBUG)
        self._handler = logging.StreamHandler(sys.stderr)
        self._handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))

        if not self._use_obj_store and not self._use_metadata_size:
            warnings.warn(
                "You are not using the object store, so function return-values get "
                "serialized into the metadata, but you are also not using "
                "the metadata size for eviction. This will likely lead to "
                "an unbounded cache. If you care about the boundedness, set "
                "either `use_obj_store` or `use_metadata_size`. ",
                UserWarning,
            )

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
                self.group._pickler  # pylint: disable=protected-access
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
            self._func,
            self.pickler,
            # Group is a "friend class", so pylint disable
            self.group._obj_store,  # pylint: disable=protected-access
            GetAttr[Callable[[], Any]]()(self._func, "__version__", lambda: None)(),
        ) + none_tuple(self._extra_func_state(self._func))

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
                type(val), "__cache_key__", identity
            )(val)
            for key, val in self._combine_args(*args, **kwargs).items()
        }

    def _args2ver(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> Any:
        return {
            key: GetAttr[Callable[[Any], Any]]()(
                type(val), "__cache_ver__", Constant(())
            )(val)
            for key, val in self._combine_args(*args, **kwargs).items()
        }

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
                self.group._key_gen  # pylint: disable=protected-access
            )
            self.group._obj_store[  # pylint: disable=protected-access
                stored_value
            ] = value_ser
        else:
            stored_value = value
            data_size = bitmath.Byte(0)

        stop = datetime.datetime.now()

        # TODO: cache stdout?

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

            key = self.key(*args, **kwargs)

            if self.group._fine_grain_persistence:
                self.group._index_read()

            if key in self.group._index:
                self._logger.debug("hit %s, %s", args, kwargs)
                entry = self.group._index[key]
                if entry.obj_store:
                    value = cast(
                        FuncReturn,
                        self.pickler.loads(
                            self.group._obj_store[cast(int, entry.value)]
                        ),
                    )
                else:
                    value = cast(FuncReturn, entry.value)
                self.time_saved += entry.time_saved
                self.group._replacement_policy.access(key, entry)
            else:
                self._logger.debug("miss %s, %s", args, kwargs)
                entry, value = self._recompute(*args, **kwargs)
                if self._use_metadata_size:
                    entry.data_size += bitmath.Byte(len(self.group._pickler.dumps(entry)))
                    entry.data_size += bitmath.Byte(len(self.group._pickler.dumps(key)))
                self.group._index[key] = entry
                self.group._replacement_policy.add(key, entry)

            if self.group._fine_grain_eviction:
                self.group._evict()

            if self.group._fine_grain_persistence:
                self.group._index_write()

            stop = datetime.datetime.now()
            self.time_cost += stop - start

            if self.time_saved < self.time_cost and self.time_cost.total_seconds() > 5:
                warnings.warn(
                    f"Caching {self._func} cost {self.time_cost.total_seconds():.1f}s but only saved {self.time_saved.total_seconds():.1f}s",
                    UserWarning,
                )

            return value

    def _compress(self, obj: Any) -> Any:
        if self._lossy_compression:
            return determ_hash(obj)
        else:
            return obj

    def key(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> tuple[Any, Any, Any, Any, Any]:
        # Note that the system state and name or so small already, it isn't worth hashing them.
        # They are also used by other Memoized functions in the same MemoizedGroup.
        # We will only hash the potentially large key items that are used exclusively by this Memoized function.
        return (
            # Group is a friend class, hence type ignore
            hashable(self.group._system_state()),  # pylint: disable=protected-access
            hashable(self._name),
            self._compress(hashable(self._func_state())),
            self._compress(hashable(self._args2key(*args, **kwargs))),
            self._compress(hashable(self._args2ver(*args, **kwargs))),
        )

    def would_hit(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> bool:
        if self.group._fine_grain_persistence:  # pylint: disable=protected-access
            self.group._index_read() # pylint: disable=protected-access

        key = self.key(*args, **kwargs)
        return key in self.group._index # pylint: disable=protected-access

# TODO: work for methods (@memoize def foo(self) ...)
