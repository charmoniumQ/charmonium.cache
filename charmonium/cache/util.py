from __future__ import annotations
import math
import random
import pickle as pickle_
from pathlib import Path
import typing
from typing import (
    Generic,
    TypeVar,
    Callable,
    Protocol,
    Optional,
    Any,
    Union,
    cast,
)
import warnings

import dill as dill_  # type: ignore

T = TypeVar("T")


class Pickler:
    def loads(self, buffer: bytes) -> Any:
        ...

    def dumps(self, val: Any) -> bytes:
        ...


dill = cast(Pickler, dill_)
pickle = cast(Pickler, pickle_)


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


PathLikeSources = Union[str, PathLike]


def PathLike_from(path: PathLikeSources) -> PathLike:
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


class KeyGen:
    """Generates unique keys (not cryptographically secure)."""

    def __init__(self, key_bits: int) -> None:
        self.key_bits = key_bits
        self.key_bytes = int(math.ceil(key_bits / 8))
        self.key_space = 2 ** self.key_bits
        self.counter = 0

    def __iter__(self) -> KeyGen:
        return self

    def __next__(self) -> int:
        """Generates a new key."""
        self.counter += 1
        if self.counter % 1000 == 0:
            prob = self.probability_of_collision(self.counter)
            if prob > 1e-6:
                warnings.warn(f"Probability of key collision is {prob:0.7f}; Consider using more than {self.key_bits} bits.", UserWarning)
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


Key = TypeVar("Key")
Val = TypeVar("Val")

class ObjStore(Sizeable, Generic[Key, Val]):
    def __setitem__(self, key: Key, val: Val) -> None:
        ...

    def __getitem__(self, key: Key) -> Val:
        ...

    def __delitem__(self, key: Key) -> None:
        ...

def constant(val: T) -> Callable[..., T]:
    def fn(*args: Any, **kwargs: Any) -> T:
        return val
    return fn


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

    @classmethod
    def create(
            cls: type[Future[T]],
            result: Union[T, Sentinel] = empty_result_sentinel,
            result_thunk: Optional[Callable[[], T]] = None,
    ) -> T:
        return cast(T, Future(result, result_thunk))
