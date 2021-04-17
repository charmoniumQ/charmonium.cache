from __future__ import annotations

import atexit
import datetime
# import functools
import heapq
import itertools
import logging
import pickle
import sys
import threading
import warnings
from typing import Any, Callable, Final, Generic, Iterator, Mapping, Union, cast

import attr
import bitmath

from .func_version import func_version
from .index import Index, IndexKeyType
from .obj_store import DirObjStore, ObjStore
from .policies import Entry, policies
from .readers_writer_lock import FastenerReadersWriterLock, Lock, ReadersWriterLock
from .util import (
    Constant,
    FuncParams,
    FuncReturn,
    Future,
    GetAttr,
    KeyGen,
    Pickler,
    Sentinel,
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


LOCK_PATH = ".cache_lock"
OBJ_STORE_PATH = ".cache"


# pyright thinks attrs has ambiguous overload
@attr.frozen  # type: ignore
class MemoizedGroup:

    # somehow, pyright does not like
    #     attr.ib(factory=Index)
    # It wants a Callable[[], Index] instead of a Type[index].
    _index: Index[Any, Entry] = attr.ib(
        init=False,
        default=Index[Any, Entry](
            (
                IndexKeyType.MATCH,  # system state
                IndexKeyType.LOOKUP,  # func name
                IndexKeyType.MATCH,  # func state
                IndexKeyType.LOOKUP,  # args key
                IndexKeyType.MATCH,  # args version
            )
        ),
    )

    _obj_store: ObjStore = attr.ib(
        # pyright doesn't know about attrs __init__, hence type ignore
        factory=lambda: DirObjStore(path=OBJ_STORE_PATH)  # type: ignore
    )

    _key_gen: KeyGen = attr.ib(factory=lambda: KeyGen())

    _size: int = attr.ib(
        default=int(bitmath.MiB(1).to_Byte().value),
        converter=lambda x: x if isinstance(x, int) else bitmath.parse_string(x),
    )

    _pickler: Pickler = pickle
    # TODO: how does end-user know Pickler type?

    _lock: ReadersWriterLock = attr.ib(
        factory=lambda: FastenerReadersWriterLock(
            LOCK_PATH
            # pyright doesn't know attrs __init__, hence type ignore
        )   # type: ignore
    )

    _fine_grain_persistence: bool = False

    _fine_grain_eviction: bool = False

    _index_key: int = attr.ib(default=0, init=False)

    def _index_read(self) -> None:
        with self._lock.reader:
            if self._index_key in self._obj_store:
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

    def __attrs_post_init__(self) -> None:
        # TODO: Can I delay this until we know the Memoized Group for sure?
        self._index_read()
        atexit.register(self._index_write)

    _extra_system_state: Callable[[], Any] = Constant(None)

    def _system_state(self) -> Any:
        """Functions are deterministic with (global state, function-specific state, args key, args version).

        - The system_state contains:
          - Package version

        """
        return (__version__, self._extra_system_state())

    # TODO: Take by string
    _eval_func: Callable[[Entry], float] = policies["luv"]

    def _evict(self) -> None:
        heap = list[tuple[float, tuple[Any, ...], Entry]]()
        total_size = 0

        for key, entry in self._index.items():
            heapq.heappush(heap, (self._eval_func(entry), key, entry))
            total_size += entry.data_size

        while total_size > self._size:
            _, key, entry = heap.pop()
            if entry.obj_store:
                del self._obj_store[entry.value]
            total_size -= entry.data_size
            del self._index[key]

    _use_count: Iterator[int] = itertools.count()


DEFAULT_MEMOIZED_GROUP = Future[MemoizedGroup](fulfill_twice=True)
# TODO: Can I delay instantiating DirObjStore until I know that I am using it?
DEFAULT_MEMOIZED_GROUP.fulfill(MemoizedGroup())

GROUP_DEFAULT = Sentinel()


# pyright thinks attrs has ambiguous overload
@attr.define  # type: ignore
class Memoized(Generic[FuncParams, FuncReturn]):
    def __attrs_post_init__(self) -> None:
        # functools.update_wrapper(self, self._func)
        if self._name == "":
            self._name = f"{self._func.__module__}.{self._func.__qualname__}"
        self._logger = logging.getLogger("charmonium.cache").getChild(self._name)
        self._logger.setLevel(logging.DEBUG)
        self._handler = logging.StreamHandler(sys.stderr)
        self._handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
        if self._verbose:
            atexit.register(self.print_usage_report)
            self.enable_logging()

    def print_usage_report(self) -> None:
        cost = self.time_cost.total_seconds()
        saved = self.time_saved.total_seconds()
        net_saved = saved - cost
        print(
            f"Caching {self._func}: cost {cost:.1f}s, saved {saved:.1f}s, net saved {net_saved:.1f}s",
            file=sys.stderr,
        )

    _func: Callable[FuncParams, FuncReturn]

    _group: Future[MemoizedGroup] = DEFAULT_MEMOIZED_GROUP

    _name: str = ""

    # TODO: make this accept default_group_verbose = Sentinel()
    _verbose: bool = True

    _apply_obj_store: Callable[FuncParams, bool] = Constant(True)

    _return_val_pickler: Union[Sentinel, Pickler] = attr.ib(default=GROUP_DEFAULT)

    _lock: Lock = threading.RLock()

    _logger: logging.Logger = attr.ib(init=False)
    _handler: logging.Handler = attr.ib(init=False)

    time_cost: datetime.timedelta = attr.ib(init=False, default=datetime.timedelta())
    time_saved: datetime.timedelta = attr.ib(init=False, default=datetime.timedelta())

    @property
    def return_val_pickler(self) -> Pickler:
        if isinstance(self._return_val_pickler, Sentinel):
            return (
                # Group is a "friend class", hence pylint disable
                self._group._._pickler  # pylint: disable=protected-access
            )
        else:
            return self._return_val_pickler

    _use_metadata_size: bool = False
    """Whether to include the size of the metadata in the size threshold calculation for eviction"""

    _extra_func_state: Callable[[Callable[FuncParams, FuncReturn]], Any] = cast(
        "Callable[[Callable[FuncParams, FuncReturn]], Any]", Constant(None)
    )

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
            pickle.dumps(func_version(self._func)),
            # cloudpickle.dumps(self._func),
            GetAttr[str]()(
                self.return_val_pickler, "__name__", "", check_callable=False
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

    _extra_args2key: Callable[FuncParams, Any] = Constant(None)

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
                    key: GetAttr[Callable[[], Any]]()(
                        val, "__cache_key__", Constant(val)
                    )()
                    # TODO: Use __persistent_hash__ instead of Constant(val)
                    for key, val in self._combine_args(*args, **kwargs).items()
                }.items()
            ),
            self._extra_args2key(*args, **kwargs),
        )

    _extra_args2ver: Callable[FuncParams, Any] = Constant(None)

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
                    key: GetAttr[Callable[[], Any]]()(
                        val, "__cache_ver__", Constant(None)
                    )()
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
        apply_obj_store = self._apply_obj_store(*args, **kwargs)

        mid = datetime.datetime.now()

        if apply_obj_store:
            value_ser = self.return_val_pickler.dumps(value)
            data_size = len(value_ser)
            # Group is a "friend class", hence pylint disable
            stored_value = next(
                self._group._._key_gen  # pylint: disable=protected-access
            )
            self._group._._obj_store[  # pylint: disable=protected-access
                stored_value
            ] = value_ser
        else:
            stored_value = value
            data_size = 0

        stop = datetime.datetime.now()

        # Returning value in addition to Entry elides the redundant `loads(dumps(...))` when obj_store is True.
        return (
            # pyright doesn't know attrs __init__, hence type ignore
            Entry(  # type: ignore
                data_size=data_size,
                recompute_time=stop - start,
                time_saved=mid - start,
                value=stored_value,
                obj_store=apply_obj_store,
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
                entry = self._group._._index[key]
                if entry.obj_store:
                    value = cast(
                        FuncReturn,
                        self.return_val_pickler.loads(
                            self._group._._obj_store[cast(int, entry.value)]
                        ),
                    )
                else:
                    value = cast(FuncReturn, entry.value)
                self.time_saved += entry.time_saved
            else:
                entry, value = self._recompute(*args, **kwargs)
                if self._use_metadata_size:
                    entry.data_size += len(self._group._._pickler.dumps(entry))
                    entry.data_size += len(self._group._._pickler.dumps(key))
                self._group._._index[key] = entry
                # TODO: Propagate possible from index to obj_store.

            entry.last_use = datetime.datetime.now()
            # entry.last_use_count = next(self._group._._use_count)

            if self._group._._fine_grain_eviction:
                self._group._._evict()

            if self._group._._fine_grain_persistence:
                self._group._._index_write()

            stop = datetime.datetime.now()
            self.time_cost += stop - start
            # TODO: persist time_cost, time_saved, date_began.

            if self.time_saved < self.time_cost and self.time_cost.total_seconds() > 5:
                warnings.warn(
                    f"Caching {self._func} cost {self.time_cost.total_seconds():.1f}s but only saved {self.time_saved.total_seconds():.1f}s",
                    UserWarning,
                )

            return value

    def would_hit(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> bool:
        key = (
            self._group._._system_state(),
            self._name,
            self._func_state(),
            self._args2key(*args, **kwargs),
            self._args2ver(*args, **kwargs),
        )

        if self._group._._fine_grain_persistence:
            self._group._._index_read()

        return key in self._group._._index
