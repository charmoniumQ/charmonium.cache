from __future__ import annotations
import random
import pickle as pickle_
import os
from pathlib import Path
import math
import typing
from typing import (
    TYPE_CHECKING,
    Generic,
    TypeVar,
    Protocol,
    Any,
    Union,
    Optional,
    cast,
    Iterable,
)
import warnings

import attr
import dill as dill_

T = TypeVar("T")

# Thanks Eric Traut
# https://github.com/microsoft/pyright/discussions/1763#discussioncomment-617220
if TYPE_CHECKING:
    from typing_extensions import ParamSpec
    FuncParams = ParamSpec("FuncParams")
else:
    FuncParams = TypeVar("FuncParams")

FuncReturn = TypeVar("FuncReturn")

class Pickler:
    def loads(self, buffer: bytes) -> Any:
        ...

    def dumps(self, val: Any) -> bytes:
        ...


dill = cast(Pickler, dill_)
pickle = cast(Pickler, pickle_)


# PathLikeSubclass = TypeVar("PathLikeSubclass", bound=PathLike)
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

    def mkdir(self, *, parents: bool = ..., exist_ok: bool = ...) -> None:
        ...

    def unlink(self) -> None:
        ...

    def iterdir(self) -> Iterable[PathLike]:
        ...

    def stat(self) -> os.stat_result:
        ...

    @property
    def parent(self) -> PathLike:
        ...

    def exists(self) -> bool:
        ...

    @property
    def name(self) -> str:
        ...

PathLikeSources = Union[str, PathLike]

def PathLike_from(path: PathLikeSources) -> PathLike:
    if isinstance(path, str):
        return Path(path)
    elif isinstance(path, PathLike):
        return path
    else:
        raise TypeError(f"Unable to interpret {path} as a PathLike.")


class Sizeable(Protocol):
    """A protocol for determining storage space usage.

    This way, the storage of the whole can be computed from the size
    of its parts.

    """

    def __size__(self) -> int:
        ...


@attr.s  # type: ignore (pyright: attrs ambiguous overload)
class KeyGen:
    """Generates unique keys (not cryptographically secure)."""

    key_bytes: int = attr.ib(default=8)
    tolerance: float = attr.ib(default=1e-6)
    counter: int = 0
    key_space: int = 0

    def __attrs_post_init__(self) -> None:
        self.key_space = 256 ** self.key_bytes

    def __iter__(self) -> KeyGen:
        return self

    def __next__(self) -> int:
        """Generates a new key."""
        self.counter += 1
        if self.counter % 100 == 0:
            prob = self.probability_of_collision(self.counter)
            if prob > self.tolerance:
                warnings.warn(
                    f"Probability of key collision is {prob:0.7f}; Consider using more than {self.key_bytes} key bytes.",
                    UserWarning,
                )
        return random.randint(0, self.key_space - 1)

    def probability_of_collision(self, keys: int) -> float:
        """Use to assert the probability of collision is acceptable."""
        return 1 - math.exp(-keys * (keys - 1) / (2 * self.key_space))


class Constant(Generic[FuncParams, FuncReturn]):
    def __init__(self, val: FuncReturn):
        self.val = val
    def __call__(self, *args: FuncParams.args, **kwargs: FuncParams.kwargs) -> FuncReturn:
        return self.val


class Sentinel:
    pass


class Future(Generic[T]):
    def __init__(self, fulfill_twice: bool = False) -> None:
        self.computed = False
        self.value: Optional[T] = None
        self.fulfill_twice = fulfill_twice

    def unwrap(self) -> T:
        if not self.computed:
            raise ValueError("Future is not yet fulfilled.")
        else:
            print(f"{self.value=}")
            return cast(T, self.value)

    @property
    def _(self) -> T:
        return self.unwrap()

    def fulfill(self, value: T) -> None:
        if self.computed and not self.fulfill_twice:
            raise ValueError("Cannot fulfill this future twice.")
        else:
            self.value = value
            self.computed = True


class GetAttr(Generic[T]):
    """When you want to getattr or use a default, with static types.

    Example: obj_hash = GetAttr[Callable[[], int]]()(obj, "__hash__", lambda: hash(obj))()

    """

    error = Sentinel()

    def __init__(self) -> None: ...
    def __call__(self, obj: object, attr: str, default: Union[T, Sentinel] = error, check_callable: bool = True) -> T:
        if hasattr(obj, attr):
            attr_val = getattr(obj, attr)
            if check_callable and not hasattr(attr_val, "__call__"):
                raise TypeError(f"Expected ({obj!r}).{attr} to be callable, but it is {type(attr_val)}.")
            else:
                return cast(T, attr_val)
        elif not isinstance(default, Sentinel):
            return default
        else:
            raise AttributeError(f"{obj!r}.{attr} does not exist, and no default was provided")
