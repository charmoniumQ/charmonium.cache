from __future__ import annotations

import abc
import contextlib
import datetime
import functools
import logging
import pickle
import shutil
import sys
import threading
import zlib
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Generic,
    Hashable,
    Optional,
    Tuple,
    TypeVar,
    cast,
)

from .types import PathLike, RLockLike, Serializable, Serializer, UserDict
from .util import (
    UNIX_TS_ZERO,
    PotentiallyPathLike,
    injective_str,
    modtime_recursive,
    pathify,
    to_hashable,
)

CacheKey = TypeVar("CacheKey")
CacheReturn = TypeVar("CacheReturn")
# CacheFunc = TypeVar('CacheFunc', bound=Callable[..., CacheReturn])
CacheFunc = TypeVar("CacheFunc", bound=Callable[..., Any])


def decor(
    obj_store: Callable[
        [str, logging.Logger], ObjectStore[CacheKey, Tuple[Any, CacheReturn]]
    ],
    lock: Optional[RLockLike] = None,
    state_fn: Optional[Callable[..., Any]] = None,
    name: Optional[str] = None,
    verbose: bool = False,
    use_module_name: bool = True,
) -> Callable[[CacheFunc], Cache[CacheFunc]]:
    """Cache a `function` in the given `obj_store`

    Instances of Cache are callable with the same signature as the
    `function` which is cached.

    `obj_store` is like a bag-check. It converts the arguments to a
    key and stores the returned value at that key. See `ObjectStore`
    for the interface.

    This is threadsafe, but only one thread can be computing a cached
    function at a time for the same. `lock` can be passed in for
    multiprocessed synchronization. It should be a context manager,
    and it should be re-entrant.

    `state_fn` is called with the same arguments as `function` returns
    the state of the environment for the computation. The state is
    like an extra argument (if it changes, the cache is invalidated)
    except that objects corresponding to an old-state are deleted when
    they are encountered; consuming the state as an extra argument
    would store both.

    The same name results in the same cache, so this class uses the
    name of the function and its module as `name`. This can be
    overriden by explicitly passing `name`.

    A note on `state_fn`. Some functions might choose to consume the
    state as an argument. Here is why you might want to use a
    `state_fn` instead.

        # TODO: Make doctest

        # Suppose you consume the state as an argument
        @decor(...)
        def f(arg, state):
            ...

        f(arg, state) # suppose this returns `result`

        # suppose `state` changes to `new_state`

        f(arg, new_state) # suppose this returns `result2`

        Now the cache contains *both* versions of result:

        {(arg, state): result1, (arg, new_state): result2}

        when you don't really need the stale `result1`. Instead with
        `state_fn`:

        @decor(..., state_fn=state_fn)
        def f(arg):
            ...

        # suppose `state_fn` returns `state`
        f(arg) # suppose this returns `result`

        # suppose the state changes for some reason,
        # and accordingly `state_fn` returns `new_state`

        f(arg) # this calls `f` again (new state invalidates the cache)
        # suppose it returns `result2`

        # but the key is _replaced_, so the cache is `{(arg, new_state): result2}`

    Example use cases:

    - the f.__code__ could be considered state. When it is changed, we
      want to replace stale cached values.

    - a file's modtime could be considered state. When it is newer, we
      want to replace stale cached values.

    """

    _lock = lock if lock is not None else threading.RLock()
    _state_fn = (
        state_fn
        if state_fn is not None
        else cast(Callable[..., Any], lambda *args, **kwargs: None)
    )

    def decor_(function: CacheFunc) -> Cache[CacheFunc]:
        return cast(
            Cache[CacheFunc],
            functools.wraps(function)(
                Cache(
                    function,
                    obj_store,
                    _lock,
                    _state_fn,
                    name,
                    verbose,
                    use_module_name,
                )
            ),
        )

    return decor_


class Cache(Generic[CacheFunc]):
    # pylint: disable=too-many-arguments
    def __init__(
        self,
        function: CacheFunc,
        obj_store: Callable[
            [str, logging.Logger], ObjectStore[CacheKey, Tuple[Any, CacheReturn]]
        ],
        lock: RLockLike,
        state_fn: Callable[..., Any],
        name: Optional[str] = None,
        verbose: bool = False,
        use_module_name: bool = True,
    ) -> None:
        self.function = function
        if name:
            self.name = name
        else:
            if use_module_name:
                self.name = f"{self.function.__module__}.{self.function.__qualname__}"
            else:
                self.name = self.function.__qualname__
        self.logger = logging.getLogger("charmonium.cache").getChild(self.name)
        self.logger.setLevel(logging.DEBUG)
        self.handler = logging.StreamHandler(sys.stderr)
        self.handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
        if verbose:
            self.enable_logging()
        self.obj_store = obj_store(self.name, self.logger)
        self.lock = lock
        self.state_fn = state_fn
        self.__qualname__ = f"Cache({self.name})"
        self.__name__ = self.__qualname__
        self._disable = False

    def __call__(self, *pos_args: Any, **kwargs: Any) -> Any:
        if self._disable:
            return self.function(*pos_args, **kwargs)
        else:
            with self.lock:
                args_key = self.obj_store.args2key(pos_args, kwargs)
                state = self.state_fn(*pos_args, **kwargs)
                if args_key in self.obj_store:
                    old_state, res = self.obj_store[args_key]
                    if old_state == state:
                        self.logger.getChild("hit").debug(
                            "%s: hit with args: %.30s, %.30s", self.name, pos_args, kwargs
                        )
                        return res
                    else:
                        self.logger.getChild("miss").debug(
                            "%s: miss with args: %.30s, %.30s due to state (%.30s -> %.30s)",
                            self.name,
                            pos_args,
                            kwargs,
                            old_state,
                            state,
                        )
                        res = self.function(*pos_args, **kwargs)
                        self.obj_store[args_key] = state, res
                else:
                    self.logger.getChild("miss").debug(
                        "%s: miss with %.30s, %.30s", self.name, pos_args, kwargs
                    )
                    res = self.function(*pos_args, **kwargs)
                    self.obj_store[args_key] = state, res
                return res

    def enable_logging(self) -> None:
        self.logger.addHandler(self.handler)

    def disable_logging(self) -> None:
        self.logger.removeHandler(self.handler)

    def clear(self) -> None:
        """Removes all cached items"""
        self.logger.getChild("clear").debug(
            "%s: clear", self.name,
        )
        self.obj_store.clear()

    def __str__(self) -> str:
        store_type = type(self.obj_store).__name__
        return f"Cache of {self.name} with {store_type}"

    @contextlib.contextmanager
    def disabled(self) -> Generator[None, None, None]:
        """Context for which caching is disabled."""
        previously_disabled = self._disable
        self._disable = True
        yield
        self._disable = previously_disabled


ObjectStoreKey = TypeVar("ObjectStoreKey")
ObjectStoreValue = TypeVar("ObjectStoreValue")


class ObjectStore(UserDict[ObjectStoreKey, ObjectStoreValue], abc.ABC):
    """ObjectStore is the dict-like backing of a Cache object"""

    @classmethod
    def create(
        cls, *args: Any, **kwargs: Any
    ) -> Callable[[str, logging.Logger], ObjectStore[ObjectStoreKey, ObjectStoreValue]]:
        """This is a curried init.

This way, you can pass the args in now, and the name in later

        """

        @functools.wraps(cls)
        def create_(
            name: str, logger: logging.Logger
        ) -> ObjectStore[ObjectStoreKey, ObjectStoreValue]:
            return cls(*args, name=name, logger=logger, **kwargs)  # type: ignore

        return create_

    def __init__(self, name: str, logger: logging.Logger) -> None:
        super().__init__()
        self.name = name
        self.logger = logger

    @abc.abstractmethod
    def args2key(
        self, _args: Tuple[Any, ...], _kwargs: Dict[str, Any],
    ) -> ObjectStoreKey:
        """Converts args to a key where this object will be kept, like a coat-check."""
        # pylint: disable=no-self-use
        ...


class MemoryStore(ObjectStore[Hashable, Any]):
    """ObjectStore backed in RAM for the duration of the program"""

    def __init__(self, name: str, logger: logging.Logger):
        # pylint: disable=non-parent-init-called
        ObjectStore.__init__(self, name, logger)

    def args2key(self, args: Tuple[Any, ...], kwargs: Dict[str, Any],) -> Hashable:
        # pylint: disable=no-self-use
        return to_hashable((args, kwargs))


class FileStore(ObjectStore[Hashable, Serializable]):
    """ObjectStore backed in one file

Data backed in ``${CACHE_PATH}/${FUNCTION_NAME}_cache.pickle``

Because this uses one file for all function-value, this is appropriate
when the function returns small objects.

The entire store (dict of function-args -> function-value) is loaded
on the first call.

    """

    def __init__(
        self,
        cache_path: PotentiallyPathLike,
        name: str,
        logger: logging.Logger,
        suffix: bool = True,
        serializer: Optional[Serializer] = None,
    ):
        # pylint: disable=non-parent-init-called,super-init-not-called
        ObjectStore.__init__(self, name, logger)
        if serializer is None:
            self.serializer = cast(Serializer, pickle)
        else:
            self.serializer = serializer
        self.cache_path = pathify(cache_path) / (
            self.name + ("_cache.pickle" if suffix else "")
        )
        self.loaded = False
        self.data = cast(Dict[Hashable, Serializable], {})

    def _load_if_not_loaded(self) -> None:
        if not self.loaded:
            self.loaded = True
            if self.cache_path.exists():
                with self.cache_path.open("rb") as fil:
                    self.data = self.serializer.load(fil)
            else:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.data = {}

    def args2key(self, args: Tuple[Any, ...], kwargs: Dict[str, Any],) -> Hashable:
        # pylint: disable=no-self-use
        return to_hashable((args, kwargs))

    def _commit(self) -> None:
        self._load_if_not_loaded()
        if self.data:
            with self.cache_path.open("wb") as fil:
                self.serializer.dump(self.data, fil)
        else:
            if self.cache_path.exists():
                self.cache_path.unlink()

    def __contains__(self, key: Hashable) -> bool:
        self._load_if_not_loaded()
        return super().__contains__(key)

    def __setitem__(self, key: Hashable, obj: Serializable) -> None:
        self._load_if_not_loaded()
        super().__setitem__(key, obj)
        self._commit()

    def __delitem__(self, key: Hashable) -> None:
        self._load_if_not_loaded()
        super().__delitem__(key)
        self._commit()

    def clear(self) -> None:
        self._load_if_not_loaded()
        super().clear()
        self._commit()


class DirectoryStore(ObjectStore[PathLike, Serializable]):
    """ObjectStore backed in one directory.

Data stored in: ``${CACHE_PATH}/${FUNCTION_NAME}/${injective_str(args)}.pickle``

Because this uses one file for each function-value and lazily loads
function-values, this is appropriate when the function returns a large
object.

    """

    def __init__(
        self,
        object_path: PotentiallyPathLike,
        name: str,
        logger: logging.Logger,
        serializer: Optional[Serializer] = None,
    ) -> None:
        # pylint: disable=non-parent-init-called
        ObjectStore.__init__(self, name, logger)
        if serializer is None:
            self.serializer = cast(Serializer, pickle)
        else:
            self.serializer = serializer
        self.cache_path = pathify(object_path) / self.name
        self.cache_path.mkdir(exist_ok=True, parents=True)

    def args2key(self, args: Tuple[Any, ...], kwargs: Dict[str, Any],) -> PathLike:
        # TODO: make an option to use hashes always here
        # Opaque file names but faster to compute
        # because recursive hashing instead of string concat
        if kwargs:
            args += (kwargs,)
        fname = f"{injective_str(args)}.pickle".replace("/", "")
        if len(fname) > 255:
            self.logger.getChild(self.__class__.__name__).debug(
                "name too long; switching to hash: %s", fname[:50]
            )
            fname = f"{zlib.adler32(fname.encode())}.pickle"
        return self.cache_path / fname

    def __setitem__(self, path: PathLike, obj: Serializable) -> None:
        with path.open("wb") as fil:
            self.serializer.dump(obj, fil)

    def __delitem__(self, path: PathLike) -> None:
        path.unlink()

    def __getitem__(self, path: PathLike) -> Serializable:
        with path.open("rb") as fil:
            return self.serializer.load(fil)

    def __contains__(self, path: Any) -> bool:
        if hasattr(path, "exists"):
            return bool(path.exists())
        else:
            return False

    def clear(self) -> None:
        if hasattr(self.cache_path, "rmtree"):
            cast(Any, self.cache_path).rmtree()
        else:
            shutil.rmtree(str(self.cache_path))
        self.cache_path.mkdir()


def make_file_state_fn(*files: PotentiallyPathLike) -> Callable[..., datetime.datetime]:
    """Declares that the state depends on the modtime of files.

Directories are scanned recursively for there most recently modified
file.

    """

    paths = list(map(pathify, files))
    if paths:

        def state_fn(*_args: Any, **_kwargs: Any) -> datetime.datetime:
            return max(map(modtime_recursive, paths))

        return state_fn
    else:

        def state_fn(*_args: Any, **_kwargs: Any) -> datetime.datetime:
            return UNIX_TS_ZERO

        return state_fn


def make_code_state_fn(function: Callable[..., Any]) -> Callable[..., bytes]:
    code = function.__code__.co_code

    def state_fn(*_args: Any, **_kwargs: Any) -> bytes:
        return code

    return state_fn


def make_combined_state_fn(*state_fns: Callable[..., Any]) -> Any:
    def state_fn(*args: Any, **kwargs: Any) -> Tuple[Any, ...]:
        return tuple(state_fn(*args, **kwargs) for state_fn in state_fns)

    return state_fn
