from __future__ import annotations

import math
import os
import random
import typing
import warnings
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Iterable,
    Optional,
    Protocol,
    TypeVar,
    Union,
    cast,
)

import attr

_T = TypeVar("_T")

# Thanks Eric Traut
# https://github.com/microsoft/pyright/discussions/1763#discussioncomment-617220
if TYPE_CHECKING:
    # ParamSpec is just for type checking, hence pylint disable
    from typing_extensions import ParamSpec  # pylint: disable=no-name-in-module

    FuncParams = ParamSpec("FuncParams")
else:
    FuncParams = TypeVar("FuncParams")

FuncReturn = TypeVar("FuncReturn")


class Pickler(Protocol):
    def loads(self, buffer: bytes) -> Any:
        ...

    def dumps(self, obj: Any) -> bytes:
        ...


# TODO: adapter for joblib's Pickler?


_PathLikeSubclass = Any
@typing.runtime_checkable
class PathLike(Protocol):
    """Duck type of `pathlib.Path`_

    .. _`pathlib.Path`: https://docs.python.org/3/library/pathlib.html#pathlib.Path"""

    def __truediv__(self, key: str) -> _PathLikeSubclass:
        """Joins a segment onto this Path."""

    def read_bytes(self) -> bytes:
        ...

    def write_bytes(self, data: bytes) -> int:
        ...

    def mkdir(self, *, parents: bool = ..., exist_ok: bool = ...) -> None:
        ...

    def unlink(self, missing_ok: bool = ...) -> None:
        ...

    def iterdir(self) -> Iterable[_PathLikeSubclass]:
        ...

    def stat(self) -> os.stat_result:
        ...

    @property
    def parent(self) -> _PathLikeSubclass:
        ...

    def exists(self) -> bool:
        ...

    def resolve(self) -> _PathLikeSubclass:
        ...

    def __fspath__(self) -> str:
        ...

    name: str


PathLikeFrom = Union[str, PathLike]


def pathlike_from(path: PathLikeFrom) -> PathLike:
    if isinstance(path, str):
        return Path(path)
    elif isinstance(path, PathLike): # type: ignore
        # somehow pyright doesn't think that a Path can be PathLike
        return path
    else:
        raise TypeError(f"Unable to interpret {path} as a PathLike.")


# pyright thinks attrs has ambiguous overload
@attr.s  # type: ignore
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

    def __repr__(self) -> str:
        return f"lambda *args,  **kwargs: {self.val}"

    def __call__(
        self, *args: FuncParams.args, **kwargs: FuncParams.kwargs
    ) -> FuncReturn:
        return self.val


class Sentinel:
    pass


class Future(Generic[_T]):
    def __init__(self, fulfill_twice: bool = False) -> None:
        self.computed = False
        self.value: Optional[_T] = None
        self.fulfill_twice = fulfill_twice

    def unwrap(self) -> _T:
        if not self.computed:
            raise ValueError("Future is not yet fulfilled.")
        else:
            return cast(_T, self.value)

    @property
    def _(self) -> _T:
        return self.unwrap()

    def fulfill(self, value: _T) -> None:
        if self.computed and not self.fulfill_twice:
            raise ValueError("Cannot fulfill this future twice.")
        else:
            self.value = value
            self.computed = True


class GetAttr(Generic[_T]):
    """When you want to getattr or use a default, with static types.

    Example: obj_hash = GetAttr[Callable[[], int]]()(obj, "__hash__", lambda: hash(obj))()

    """

    error = Sentinel()

    def __init__(self) -> None:
        ...

    def __call__(
        self,
        obj: object,
        attr_name: str,
        default: Union[_T, Sentinel] = error,
        check_callable: bool = True,
    ) -> _T:
        if hasattr(obj, attr_name):
            attr_val = getattr(obj, attr_name)
            if check_callable and not hasattr(attr_val, "__call__"):
                raise TypeError(
                    f"Expected ({obj!r}).{attr_name} to be callable, but it is {type(attr_val)}."
                )
            else:
                return cast(_T, attr_val)
        elif not isinstance(default, Sentinel):
            return default
        else:
            raise AttributeError(
                f"{obj!r}.{attr_name} does not exist, and no default was provided"
            )

def identity(obj: _T) -> _T:
    return obj
