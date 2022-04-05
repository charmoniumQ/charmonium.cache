from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Generic, Optional, TypeVar, Union, cast

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


class Constant(Generic[FuncParams, FuncReturn]):
    def __init__(self, val: FuncReturn):
        self.val = val

    def __repr__(self) -> str:
        return f"Constant({self.val!r})"

    def __call__(
        self, *args: FuncParams.args, **kwargs: FuncParams.kwargs
    ) -> FuncReturn:
        return self.val


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

    error = object()

    def __init__(self) -> None:
        ...

    def __call__(
        self,
        obj: object,
        attr_name: str,
        default: Union[_T, object] = error,
        check_callable: bool = False,
    ) -> _T:
        if hasattr(obj, attr_name):
            attr_val = getattr(obj, attr_name)
            if check_callable and not hasattr(attr_val, "__call__"):
                raise TypeError(
                    f"GetAttr expected ({obj!r}).{attr_name} to be callable, but it is {type(attr_val)}."
                )
            else:
                return cast(_T, attr_val)
        elif default is not GetAttr.error:
            return cast(_T, default)
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


# class DontPickle(Generic[_T]):
#     def __init__(self, init: str) -> None:
#         self.__setstate__(init)

#     def __getstate__(self) -> Any:
#         return self.init

#     def __setstate__(self, init: str) -> None:
#         self.init = init
#         self.obj = cast(_T, eval(self.init))

#     def __getattr__(self, attrib: str) -> Any:
#         return getattr(self.obj, attrib)

#     @staticmethod
#     def create(init: str) -> _T:
#         return cast(_T, DontPickle[_T](init))


def with_attr(obj: _T, attr_name: str, attr_val: Any) -> _T:
    object.__setattr__(obj, attr_name, attr_val)
    return obj


def temp_path(
    suffix: Optional[str] = None,
    prefix: Optional[str] = None,
    directory: Optional[Union[str, Path]] = None,
) -> Path:
    # TODO: Remove this function.
    temp_dir = Path(
        tempfile.TemporaryDirectory(suffix=suffix, prefix=prefix, dir=directory).name # pylint: disable=consider-using-with
    )
    return temp_dir


def ellipsize(string: str, size: int, ellipsis: str = "...") -> str:
    if size < 5:
        raise ValueError("Size is too small")
    elif len(string) < size:
        return string
    else:
        break_point = (size - len(ellipsis)) // 2
        odd = int((size - len(ellipsis)) % 2)
        return string[: (break_point + odd)] + ellipsis + string[-break_point:]
