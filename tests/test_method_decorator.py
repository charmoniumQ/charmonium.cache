from __future__ import annotations
import logging
from typing import Any, Type, List

from charmonium.cache import DirObjStore, MemoizedGroup, freeze_config, memoize
from charmonium.cache.util import temp_path

freeze_config.recursion_limit = 20


def test_instancemethod() -> None:
    class Class:
        def __init__(self, y: int) -> None:
            self.y = y

        @memoize(
            group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True),
        )
        def method(self, z: int) -> int:
            return self.y + z

    obj = Class(3)
    assert obj.method(4) == 7  # type: ignore
    assert obj.method.would_hit(obj, 4)
    obj.y = 4
    assert not obj.method.would_hit(obj, 4)
    assert obj.method(4) == 8  # type: ignore


def test_classmethod() -> None:
    class Class:
        x: List[int] = [3]

        @classmethod
        @memoize(
            group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True),
        )
        def method(cls: Type[Class], z: int) -> int:
            return cls.x[-1] + z

    assert Class.method(4) == 7  # type: ignore
    assert Class.method.would_hit(Class, 4)
    Class.x.append(4)
    assert not Class.method.would_hit(Class, 4)
    assert Class.method(4) == 8  # type: ignore


def test_staticemethod() -> None:
    class Class:
        @staticmethod
        @memoize(
            group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True),
        )
        def method(z: int) -> int:
            return z + 1

    assert Class.method(4) == 5
    assert Class.method.would_hit(4)
