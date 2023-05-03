from __future__ import annotations

import warnings
import dataclasses
import shutil
from typing import TYPE_CHECKING, Any, Iterator, Union, TypeVar
from pathlib import Path

if TYPE_CHECKING:
    from typing import Protocol
else:
    Protocol = object


_T = TypeVar("_T")


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

    def get(self, key: int, default: _T) -> Union[bytes | _T]:
        ...

    def __contains__(self, key: int) -> bool:
        """The implementation is often slow, so it will be called rarely."""

    def __iter__(self) -> Iterator[int]:
        # pylint: disable=non-iterator-returned
        ...

    def clear(self) -> None:
        ...


@dataclasses.dataclass
class DirObjStore(ObjStore):
    """Use a directory in the filesystem as an object-store.

    Each object is a file in the directory.

    Note that this directory must not contain any other files.

    """

    path: Path
    key_bytes: int

    def __frozenstate__(self) -> Any:
        return (str(self.path), self.key_bytes)

    def __init__(self, path: Union[Path, str], key_bytes: int = 16) -> None:
        """
        :param path: the directory of the object store.
        :param key_bytes: the number of bytes to use as keys
        """
        super().__init__()
        self.path = path if isinstance(path, Path) else Path(path)
        self.key_bytes = key_bytes

        if self.path.exists():
            if any(
                not self._is_key(path) and not path.name.startswith(".")
                for path in self.path.iterdir()
            ):
                raise ValueError(f"{self.path.resolve()} contains junk I didn't make.")
        else:
            self.path.mkdir(parents=True)

    def _int2str(self, key: int) -> str:
        assert key < (1 << (8 * self.key_bytes))
        return f"{key:0{2*self.key_bytes}x}"

    def _is_key(self, path: Path) -> bool:
        return len(path.name) == 2 * self.key_bytes and all(
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

    def get(self, key: int, default: _T) -> Union[bytes | _T]:
        path = self.path / self._int2str(key)
        if not path.exists():
            return default
        else:
            return path.read_bytes()

    def __contains__(self, key: int) -> bool:
        return (self.path / self._int2str(key)).exists()

    def __iter__(self) -> Iterator[int]:
        yield from (
            int(path.name, base=16)
            for path in self.path.iterdir()
            if not path.name.startswith(".") and self._is_key(path)
        )

    def clear(self) -> None:
        if hasattr(self.path, "rmtree"):
            self.path.rmtree()
        else:
            shutil.rmtree(self.path)
