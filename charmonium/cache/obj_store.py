from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Protocol

import attr

from .util import GetAttr, PathLike, PathLikeFrom, pathlike_from


class ObjStore(Protocol):
    """An `object-store`_ is a persistent mapping from int to bytes.

    .. _`object-store`: https://en.wikipedia.org/wiki/Object_storage

    """
    def __setitem__(self, key: int, val: bytes) -> None:
        ...

    def __getitem__(self, key: int) -> bytes:
        ...

    def __delitem__(self, key: int) -> None:
        ...

    def __contains__(self, key: int) -> bool:
        """The implementation is often slow, so it will be called rarely."""
        ...

    def __hash__(self) -> int:
        ...

    def clear(self) -> None:  # pylint: disable=no-self-use
        # Doesn't use self because I'm defining a Protocol
        ...


# pyright thinks attrs has ambiguous overload
@attr.frozen(init=False)  # type: ignore
class DirObjStore(ObjStore):
    """Use a directory in the filesystem as an object-store.

    Each object is a file in the directory.

    Note that this directory must not contain any other files.

    """

    path: PathLike
    _key_bytes: int

    def __init__(self, path: PathLikeFrom, key_bytes: int = 8) -> None:
        """
        :param path: a 'PathLike' object which will be the directory of the object store.
        :param key_bytes: the number of bytes to use as keys
        """
        object.__setattr__(self, "path", pathlike_from(path))
        object.__setattr__(self, "_key_bytes", key_bytes)

        if self.path.exists() and any(
            not self._is_key(path) and not path.name.startswith(".") for path in self.path.iterdir()
        ):
            bad_paths = [path for path in self.path.iterdir() if not self._is_key(path)]
            raise ValueError(
                f"{self.path.resolve()=} contains junk I didn't make: {bad_paths}"
            )

    def _int2str(self, key: int) -> str:
        assert key < (1 << (8 * self._key_bytes))
        return f"{key:0{2*self._key_bytes}x}"

    def _is_key(self, path: PathLike) -> bool:
        return len(path.name) == 2 * self._key_bytes and all(
            letter in "0123456789abcdef" for letter in path.name
        )

    def __setitem__(self, key: int, val: bytes) -> None:
        self.path.mkdir(exist_ok=True)
        (self.path / self._int2str(key)).write_bytes(val)

    def __getitem__(self, key: int) -> bytes:
        path = self.path / self._int2str(key)
        if not path.exists():
            raise KeyError(key)
        else:
            return path.read_bytes()

    def __delitem__(self, key: int) -> None:
        (self.path / self._int2str(key)).unlink(missing_ok=True)

    def __contains__(self, key: int) -> bool:
        return (self.path / self._int2str(key)).exists()

    def clear(self) -> None:
        self.path.mkdir(exist_ok=True)
        # somehow pyright doesn't think that a Path can be PathLike
        if isinstance(self.path, Path): # type: ignore
            shutil.rmtree(self.path)
        else:
            # "There is no syntax to indicate optional or keyword arguments; such function types are rarely used as callback types"
            # :'(
            # Therefore, I can't use Callable[[], None]
            GetAttr[Callable[..., None]]()(self.path, "rm")(recursive=True)
        self.path.mkdir()
