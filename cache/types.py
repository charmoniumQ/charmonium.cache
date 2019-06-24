from __future__ import annotations
from pathlib import PurePath
from typing import Iterable, Union, Any, IO, TYPE_CHECKING
from collections import UserDict as _UserDict
from typing_extensions import Protocol


# https://stackoverflow.com/a/48554601/1078199
if TYPE_CHECKING:
    # we are running in mypy
    # which understands UserDict[Key, Value]
    UserDict = _UserDict
else:
    # I need to make `UserDict` subscriptable
    # subscripting FakeUserDictMeta is a no-op
    # so `UserDict[T] is UserDict`
    class FakeUserDictMeta(type(_UserDict)): # pylint: disable=missing-docstring
        def __getitem__(cls, item):
            return cls
    class UserDict(_UserDict, metaclass=FakeUserDictMeta): # pylint: disable=missing-docstring
        pass


class PathLike(Protocol):
    '''Something that acts like pathlib.PurePath.

This can be generalized to AWS S3 or Google Cloud Storage backends

    '''

    # pylint: disable=no-self-use,unused-argument,missing-docstring
    def __truediv__(self, other: Union[str, PurePath]) -> PathLike:
        ...
    def mkdir(self, mode: int = 0, parents: bool = False, exist_ok: bool = False) -> None:
        ...
    def exists(self) -> bool:
        ...
    def unlink(self) -> None:
        ...
    def iterdir(self) -> Iterable[PathLike]:
        ...
    def open(self, mode: str = 'r') -> IO[Any]:
        ...
    @property
    def parent(self) -> PathLike:
        ...


Serializable = Any # pylint: disable=invalid-name


class Serializer(Protocol):
    '''Something that acts like pickle.'''

    # pylint: disable=no-self-use,unused-argument,missing-docstring
    def load(self, fil: IO[bytes]) -> Serializable:
        ...
    def dump(self, obj: Serializable, fil: IO[bytes]) -> None:
        ...
