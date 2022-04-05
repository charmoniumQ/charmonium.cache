from __future__ import annotations

import shutil
from typing import TYPE_CHECKING, Any, Iterator

import attr

from .pathlike import PathLike, PathLikeFrom, pathlike_from

if TYPE_CHECKING:
    from typing import Protocol

else:
    Protocol = object


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

    def __iter__(self) -> Iterator[int]:
        # pylint: disable=non-iterator-returned
        ...

    def clear(self) -> None:
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

    def __determ_hash__(self) -> Any:
        return (str(self.path), self._key_bytes)

    def __init__(self, path: PathLikeFrom, key_bytes: int = 16) -> None:
        """
        :param path: a 'PathLike' object which will be the directory of the object store.
        :param key_bytes: the number of bytes to use as keys
        """
        super().__init__()
        object.__setattr__(self, "path", pathlike_from(path))
        object.__setattr__(self, "_key_bytes", key_bytes)

        if self.path.exists():
            if any(
                not self._is_key(path) and not path.name.startswith(".")
                for path in self.path.iterdir()
            ):
                raise ValueError(f"{self.path.resolve()} contains junk I didn't make.")
        else:
            self.path.mkdir(parents=True)

    def _int2str(self, key: int) -> str:
        assert key < (1 << (8 * self._key_bytes))
        return f"{key:0{2*self._key_bytes}x}"

    def _is_key(self, path: PathLike) -> bool:
        return len(path.name) == 2 * self._key_bytes and all(
            letter in "0123456789abcdef" for letter in path.name
        )

    def __setitem__(self, key: int, val: bytes) -> None:
        (self.path / self._int2str(key)).write_bytes(val)

    def __getitem__(self, key: int) -> bytes:
        path = self.path / self._int2str(key)
        if not path.exists():
            raise KeyError(key)
        else:
            return path.read_bytes()

    def __delitem__(self, key: int) -> None:
        if key in self:
            # print(f"delitem {key}")
            (self.path / self._int2str(key)).unlink()

    def __contains__(self, key: int) -> bool:
        return (self.path / self._int2str(key)).exists()

    def __iter__(self) -> Iterator[int]:
        yield from (
            int(path.name, base=16)
            for path in self.path.iterdir()
            if not path.name.startswith(".") and self._is_key(path)
        )

    def clear(self) -> None:
        # print("clear")
        if hasattr(self.path, "rmtree"):
            self.path.rmtree()  # type: ignore
        else:
            shutil.rmtree(self.path)
