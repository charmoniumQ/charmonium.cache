from __future__ import annotations
import heapq
import itertools
import logging
import functools
import sys
import atexit
import datetime
from typing import (
    Generic,
    TypeVar,
    Callable,
    Optional,
    Any,
    cast,
    Final,
    Iterator,
)
from typing_extensions import ParamSpec

import attr

from .util import constant, pickle, dill, ObjStore, Pickler, KeyGen, Future
from .index import Index
from .policies import policies, Entry


__version__ = "1.0.0"

FuncParams = ParamSpec("FuncParams")
FuncReturn = TypeVar("FuncReturn")


BYTE_ORDER: Final[str] = "big"


def memoize(
    **kwargs: Any,
) -> Callable[[Callable[FuncParams, FuncReturn]], Callable[FuncParams, FuncReturn]]:
    def actual_memoize(
        func: Callable[FuncParams, FuncReturn], /
    ) -> Callable[FuncParams, FuncReturn]:
        return Memoize[FuncParams, FuncReturn](func, **kwargs)

    return actual_memoize


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

    # TODO: Convert from string
    _eval_func: Callable[[Entry[Any]], float] = attr.ib(default=policies["LUV"])

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
