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
    Any,
    cast,
    Final,
    Iterator,
    TYPE_CHECKING,
)

import attr
from bitmath import MiB


from .util import Constant, pickle, dill, Pickler, KeyGen, Future, GetAttr
from .index import Index, IndexKeyType
from .obj_store import ObjStore, DirObjStore
from .policies import policies, Entry


__version__ = "1.0.0"

# Thanks Eric Traut
# https://github.com/microsoft/pyright/discussions/1763#discussioncomment-617220
if TYPE_CHECKING:
    from typing_extensions import ParamSpec
    FuncParams = ParamSpec("FuncParams")
else:
    FuncParams = TypeVar("FuncParams")

FuncReturn = TypeVar("FuncReturn")


BYTE_ORDER: Final[str] = "big"


def memoize(
    **kwargs: Any,
) -> Callable[[Callable[FuncParams, FuncReturn]], Memoized[FuncParams, FuncReturn]]:
    def actual_memoize(
        func: Callable[FuncParams, FuncReturn], /
    ) -> Memoized[FuncParams, FuncReturn]:
        return Memoized[FuncParams, FuncReturn](func, **kwargs)  # type: ignore (pyright doesn't know attrs __init__)

    # I believe pyright suffers from this fixed mypy bug: https://github.com/python/mypy/issues/1323
    # Therefore, I have to circumvent the type system.
    # However, somehow `cast` isn't sufficient.
    # Therefore, I need `# type: ignore`. I don't like it any more than you.
    # return cast(Memoized[FuncParams, FuncReturn], actual_memoize)
    return actual_memoize  # type: ignore (see above)


@attr.frozen  # type: ignore (pyright: attrs ambiguous overload)
class MemoizedGroup:

    # somehow, pyright does not like
    #     attr.ib(factory=Index)
    # It wants a Callable[[], Index] instead of a Type[index].
    _index: Index[Any, Entry] = Index((
        IndexKeyType.MATCH,  # system state
        IndexKeyType.LOOKUP, # func name
        IndexKeyType.MATCH,  # func state
        IndexKeyType.LOOKUP, # args key
        IndexKeyType.MATCH,  # args version
    ))

    _obj_store: ObjStore = attr.ib(factory=lambda: DirObjStore())

    _key_gen: KeyGen = attr.ib(factory=lambda: KeyGen())

    _size: int = int(MiB(1).to_Byte().value)
    # TODO: use bitmath.parse_string("4.7 GiB") or integer

    _pickler: Pickler = pickle

    _verbose: bool = True

    def __attrs_post_init__(self) -> None:
        self._index.schema = (
            IndexKeyType.MATCH, # env state
            IndexKeyType.LOOKUP, # function name
            IndexKeyType.MATCH, # function state
            IndexKeyType.LOOKUP, # args val
            IndexKeyType.MATCH, # args ver
        )
        print(self._index)
        self._index.read()
        atexit.register(self._index.write)

    _extra_system_state: Callable[[], Any] = Constant(None)

    def _system_state(self) -> Any:
        """Functions are deterministic with (global state, function-specific state, args key, args version).

        - The system_state contains:
          - Package version

        """
        return (__version__, self._extra_system_state())

    # TODO: Convert from string
    _eval_func: Callable[[Entry], float] = policies["LUV"]

    def _evict(self) -> None:
        heap = list[tuple[float, tuple[Any, ...], Entry]]()
        for key, entry in self._index.items():
            heapq.heappush(heap, (self._eval_func(entry), key, entry))
        while self._index.__size__() + self._obj_store.__size__() > self._size:
            _, key, entry = heap.pop()
            if entry.obj_store:
                del self._obj_store[entry.value]
            del self._index[key]

    _use_count: Iterator[int] = itertools.count()


DEFAULT_MEMOIZED_GROUP = Future[MemoizedGroup](fulfill_twice=True)
# DEFAULT_MEMOIZED_GROUP.fulfill(MemoizedGroup())
# TODO: fulfill default


@attr.s  # type: ignore (pyright: attrs ambiguous overload)
class Memoized(Generic[FuncParams, FuncReturn]):
    def __attrs_post_init__(self) -> None:
        functools.update_wrapper(self, self._func)
        if self._name == "":
            self._name = f"{self._func.__module__}.{self._func.__qualname__}"
        self._logger = logging.getLogger("charmonium.cache").getChild(self._name)
        self._logger.setLevel(logging.DEBUG)
        self._handler = logging.StreamHandler(sys.stderr)
        self._handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
        if self._verbose:
            self.enable_logging()

    _func: Callable[FuncParams, FuncReturn]

    _group: Future[MemoizedGroup] = DEFAULT_MEMOIZED_GROUP

    _name: str = ""

    # TODO: make this accept default_group_verbose = Sentinel()
    _verbose: bool = True

    _apply_obj_store: Callable[FuncParams, bool] = Constant(True)

    # TODO: make this accept default_group_pickler = Sentinel()
    _pickler: Pickler = pickle

    _fine_grain_eviction: bool = False
    _fine_grain_persistence: bool = False

    _extra_func_state: Callable[[Callable[FuncParams, FuncReturn]], Any] = cast("Callable[[Callable[FuncParams, FuncReturn]], Any]", Constant(None))

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
            dill.dumps(self._func),
            self._pickler,
            self._group._._obj_store,
            GetAttr[Callable[[], Any]]()(self._func, "__version__", lambda: None)(),
            self._extra_func_state(self._func),
        )

    _extra_args2key: Callable[FuncParams, Any] = Constant(None)

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
                key: GetAttr[Callable[[], Any]]()(val, "__cache_key__", lambda: val)()
                for key, val in {**dict(enumerate(args)), **kwargs}.items()
            },
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
            {
                key: GetAttr[Callable[[], Any]]()(val, "__cache_ver__", lambda: None)()
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

    def _recompute(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs,) -> Entry:
        start = datetime.datetime.now()
        value = self._func(*args, **kwargs)
        stop = datetime.datetime.now()

        value_ser = self._pickler.dumps(value)
        data_size = len(value_ser)
        apply_obj_store = self._apply_obj_store(*args, **kwargs)
        if apply_obj_store:
            key = next(self._group._._key_gen)
            self._group._._obj_store[key] = value_ser
            value_ser = key.to_bytes(self._group._._key_gen.key_bytes, BYTE_ORDER)
            data_size += len(value_ser)

        return Entry(  # type: ignore (pyright doesn't know attrs __init__)
            data_size=data_size, compute_time=stop - start, value=value, obj_store=apply_obj_store,
        )
    
    def __call__(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> FuncReturn:
        # TODO: capture overhead. Warn and log based on it.

        key = (
            self._group._._system_state(),
            self._name,
            self._func_state(),
            self._args2key(*args, **kwargs),
            self._args2ver(*args, **kwargs),
        )

        if self._fine_grain_persistence:
            self._group._._index.read()

        entry = self._group._._index.get_or(key, self._recompute)
        entry.size += len(self._pickler.dumps(key))
        entry.last_use = datetime.datetime.now()
        entry.last_use_count = next(self._group._._use_count)

        if self._fine_grain_persistence:
            with self._group._._index.read_modify_write():
                self._group._._evict()

        if self._fine_grain_eviction:
            self._group._._evict()

        value_ser = entry.value
        if entry.obj_store:
            value_key = int.from_bytes(value_ser, BYTE_ORDER)
            value_ser = self._group._._obj_store[value_key]
        value: FuncReturn = self._pickler.loads(value_ser)
        # TODO: figure out how to elide this `loads(dumps(...))`, if we did a recompute.

        return value


# TODO: thread safety
