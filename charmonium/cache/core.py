from __future__ import annotations

import abc
import contextlib
import functools
import hashlib
import logging
import pickle
import shutil
import sys
import threading
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Generic,
    Optional,
    Tuple,
    TypeVar,
    cast,
)

import cloudpickle  # type: ignore

from .types import PathLike, Serializable, Serializer, UserDict
from .util import PotentiallyPathLike, pathify

__version__ = "0.5.2"


CacheReturn = TypeVar("CacheReturn")
# CacheFunc = TypeVar('CacheFunc', bound=Callable[..., CacheReturn])
CacheFunc = TypeVar("CacheFunc", bound=Callable[..., Any])


# cloudpickle also serializes the closed-over objects
# dill does not. See tests/test_picklers.py
serialize = dill.dumps


# Should have enough bits to rarely collide.
def checksum(bytez: bytes) -> int:
    hasher = hashlib.sha1()
    hasher.update(bytez)
    return int.from_bytes(hasher.digest(), "little")


environment_key = checksum(serialize("ENVIRONMENT"))


def cache_key(obj: Any) -> Any:
    if hasattr(obj, "__cache_key__"):
        return obj.__cache_key__()
    else:
        return obj


def cache_val(obj: Any) -> Any:
    if hasattr(obj, "__cache_val__"):
        return obj.__cache_val__()
    else:
        return None


def decor(
    obj_store: Callable[[str, logging.Logger], ObjectStore[CacheReturn]],
    name: Optional[str] = None,
    verbose: bool = False,
    use_module_name: bool = True,
    version: Any = 0,
) -> Callable[[CacheFunc], Cache[CacheFunc]]:
    """Cache a `function` in the given `obj_store`

    Instances of Cache are callable with the same signature as the
    `function` which is cached.

    `obj_store` is like a bag-check. It converts the arguments to a
    key and stores the returned value at that key. See `ObjectStore`
    for the interface.

    """

    def decor_(function: CacheFunc) -> Cache[CacheFunc]:
        return cast(
            Cache[CacheFunc],
            functools.wraps(function)(
                Cache(function, obj_store, name, verbose, use_module_name, version)
            ),
        )

    return decor_


class Cache(Generic[CacheFunc]):
    # pylint: disable=too-many-arguments
    def __init__(
        self,
        function: CacheFunc,
        obj_store: Callable[[str, logging.Logger], ObjectStore[CacheReturn]],
        name: Optional[str] = None,
        verbose: bool = False,
        use_module_name: bool = True,
        version: Any = 0,
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
        self.version = version
        self.obj_store = obj_store(self.name, self.logger)
        self.lock = threading.RLock()
        self.__qualname__ = f"Cache({self.name})"
        self.__name__ = self.__qualname__
        self._disable = False
        environment = checksum(serialize((__version__, self.version, self.function)))
        if (
            environment_key not in self.obj_store
            or self.obj_store[environment_key] != environment  # type: ignore
        ):
            self.obj_store.clear()
            self.obj_store[environment_key] = environment  # type: ignore

    def __call__(self, *pos_args: Any, **kwargs: Any) -> Any:
        if self._disable:
            return self.function(*pos_args, **kwargs)
        else:
            with self.lock:
                key = checksum(
                    serialize(
                        (
                            [cache_key(arg) for arg in pos_args],
                            {key: cache_key(val) for key, val in kwargs.items()},
                        )
                    )
                )
                val = checksum(
                    serialize(
                        (
                            [cache_val(arg) for arg in pos_args],
                            {key: cache_val(val) for key, val in kwargs.items()},
                        )
                    )
                )
                if key in self.obj_store and self.obj_store[key][0] == val:
                    ret = self.obj_store[key][1]
                    self.logger.getChild("hit").debug(
                        "%s: hit with args: %.30s, %.30s",
                        self.name,
                        pos_args[1:-1],
                        kwargs,
                    )
                else:
                    self.logger.getChild("miss").debug(
                        "%s: miss with %.30s, %.30s", self.name, pos_args[1:-1], kwargs
                    )
                    ret = self.function(*pos_args, **kwargs)
                    self.obj_store[key] = val, ret
                return ret

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


ObjectStoreValue = TypeVar("ObjectStoreValue")


class ObjectStore(UserDict[int, Tuple[int, ObjectStoreValue]], abc.ABC):
    """ObjectStore is the dict-like backing of a Cache object"""

    @classmethod
    def create(
        cls, *args: Any, **kwargs: Any
    ) -> Callable[[str, logging.Logger], ObjectStore[ObjectStoreValue]]:
        """This is a curried init.

This way, you can pass the args in now, and the name in later

        """

        @functools.wraps(cls)
        def create_(name: str, logger: logging.Logger) -> ObjectStore[ObjectStoreValue]:
            return cls(*args, name=name, logger=logger, **kwargs)  # type: ignore

        return create_

    def __init__(self, name: str, logger: logging.Logger) -> None:
        super().__init__()
        self.name = name
        self.logger = logger


class MemoryStore(ObjectStore[Any]):
    """ObjectStore backed in RAM for the duration of the program"""

    def __init__(self, name: str, logger: logging.Logger):
        # pylint: disable=non-parent-init-called
        ObjectStore.__init__(self, name, logger)


class FileStore(ObjectStore[Serializable]):
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
        self.data: Dict[int, Serializable] = {}

    def _load_if_not_loaded(self) -> None:
        if not self.loaded:
            self.loaded = True
            if self.cache_path.exists():
                with self.cache_path.open("rb") as fil:
                    self.data = self.serializer.load(fil)
            else:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.data = {}

    def _commit(self) -> None:
        self._load_if_not_loaded()
        if self.data:
            with self.cache_path.open("wb") as fil:
                self.serializer.dump(self.data, fil)
        else:
            if self.cache_path.exists():
                self.cache_path.unlink()

    def __contains__(self, key: Any) -> bool:
        self._load_if_not_loaded()
        return super().__contains__(key)

    def __setitem__(self, key: int, obj: Serializable) -> None:
        self._load_if_not_loaded()
        super().__setitem__(key, obj)
        self._commit()

    def __delitem__(self, key: int) -> None:
        self._load_if_not_loaded()
        super().__delitem__(key)
        self._commit()

    def clear(self) -> None:
        self._load_if_not_loaded()
        super().clear()
        self._commit()


class DirectoryStore(ObjectStore[Serializable]):
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

    def _path(self, key: int) -> PathLike:
        return self.cache_path / f"{key:x}.pickle"

    def __setitem__(self, key: int, obj: Serializable) -> None:
        with self._path(key).open("wb") as fil:
            self.serializer.dump(obj, fil)

    def __delitem__(self, key: int) -> None:
        self._path(key).unlink()

    def __getitem__(self, key: int) -> Serializable:
        with self._path(key).open("rb") as fil:
            return self.serializer.load(fil)

    def __contains__(self, key: Any) -> bool:
        if isinstance(key, int):
            return self._path(key).exists()
        else:
            return False

    def clear(self) -> None:
        if hasattr(self.cache_path, "rmtree"):
            cast(Any, self.cache_path).rmtree()
        else:
            shutil.rmtree(str(self.cache_path))
        self.cache_path.mkdir()
