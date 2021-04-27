from __future__ import annotations

import math
import random
import warnings
from typing import TYPE_CHECKING, Any, Callable, Generic, Optional, TypeVar, Union, cast

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


# TODO: adapter for joblib's Pickler?


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
    def __init__(self, thunk: Callable[[], _T]) -> None:
        self._thunk = thunk
        self._value: Optional[_T] = None
        self.computed = False

    def unwrap(self) -> _T:
        if not self.computed:
            self.computed = True
            self._value = self._thunk()
        return cast(_T, self._value)

    def __getattr__(self, this_attr: str) -> Any:
        return getattr(self.unwrap(), this_attr)

    @classmethod
    def create(cls, thunk: Callable[[], _T]) -> _T:
        return cast(_T, cls(thunk))


class GetAttr(Generic[_T]):
    """When you want to getattr or use a default, with static types.

    Example: ``obj_hash = GetAttr[Callable[[], int]]()(obj, "__hash__", lambda: hash(obj))()``

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
                    f"GetAttr expected ({obj!r}).{attr_name} to be callable, but it is {type(attr_val)}. Add ``check_callable=False`` to ignore."
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

def none_tuple(obj: Any) -> tuple[Any, ...]:
    if obj is not None:
        return (obj,)
    else:
        return ()
