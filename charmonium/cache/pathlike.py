from __future__ import annotations

import os
import typing
from pathlib import Path
from typing import Any, Iterable, Protocol, Union

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
