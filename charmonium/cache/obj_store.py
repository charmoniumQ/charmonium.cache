from __future__ import annotations
import shutil
from pathlib import Path
from typing import Callable

import attr

from .util import Sizeable, PathLike, GetAttr, PathLike_from

class ObjStore(Sizeable):
    def __setitem__(self, key: int, val: bytes) -> None:
        ...

    def __getitem__(self, key: int) -> bytes:
        ...

    def __delitem__(self, key: int) -> None:
        ...

    def clear(self) -> None:
        ...


DEFAULT_PATH = Path(".cache_obj")


@attr.frozen  # type: ignore
class DirObjStore(ObjStore):

    path: PathLike = attr.ib(default=DEFAULT_PATH, converter=PathLike_from)
    key_bytes: int = 8

    def __attrs_post_init__(self) -> None:
        self.path.mkdir(exist_ok=True)
        if not all(self._is_key(path) for path in self.path.iterdir()):
            raise ValueError(f"{self.path} contains junk I didn't make.")

    def _int2str(self, key: int) -> str:
        assert key < 2**(8*self.key_bytes)
        return f"{key:0{self.key_bytes}x}"

    def _is_key(self, s: PathLike) -> bool:
        return len(s.name) == self.key_bytes and all(letter in "0123456789abcdef" for letter in s.name)

    def __setitem__(self, key: int, val: bytes) -> None:
        (self.path / self._int2str(key)).write_bytes(val)

    def __getitem__(self, key: int) -> bytes:
        path = (self.path / self._int2str(key))
        if not path.exists():
            raise KeyError(key)
        else:
            return path.read_bytes()

    def __delitem__(self, key: int) -> None:
        (self.path / self._int2str(key)).unlink()

    def clear(self) -> None:
        if isinstance(self.path, Path):
            shutil.rmtree(self.path)
        else:
            # "There is no syntax to indicate optional or keyword arguments; such function types are rarely used as callback types"
            # :'(
            # Therefore, I can't use Callable[[], None]
            GetAttr[Callable[..., None]]()(self.path, "rm")(recursive=True)
        self.path.mkdir()

    def __size__(self) -> int:
        return sum(
            path.stat().st_size
            for path in self.path.iterdir()
            if self._is_key(path)
        )
