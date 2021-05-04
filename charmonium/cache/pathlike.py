from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Union

if TYPE_CHECKING:
    from typing import Protocol

else:
    Protocol = object

_PathLikeSubclass = Any


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
    elif hasattr(path, "read_bytes"):
        return path
    else:
        raise TypeError(f"Unable to interpret {path} as a PathLike.")
