import logging
from typing import Type, Any
from charmonium.cache.util import temp_path
from charmonium.cache import DirObjStore, MemoizedGroup, memoize


def test_instancemethod(caplog):
    caplog.set_level(logging.DEBUG, "charmonium.cache.ops")
    class Class:
        def __init__(self, y: int) -> None:
            self.y = y

        @memoize(group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True),)
        def method(self, z: int) -> int:
            return self.y + z

    obj = Class(3)
    assert obj.method(4) == 7
    assert obj.method.would_hit(obj, 4)
    obj.y = 4
    assert not obj.method.would_hit(obj, 4)
    assert obj.method(4) == 8

def test_classmethod():
    class Class:
        x = 3

        @classmethod
        @memoize(group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True),)
        def method(cls: Type[Any], z: int) -> int:
            return cls.x + z

    assert Class.method(4) == 7
    assert Class.method.would_hit(Class, 4)
    Class.x = 4
    assert not Class.method.would_hit(Class, 4)
    assert Class.method(4) == 8

def test_staticemethod():
    class Class:
        @staticmethod
        @memoize(group=MemoizedGroup(obj_store=DirObjStore(temp_path()), temporary=True),)
        def method(z: int) -> int:
            return z + 1

    assert Class.method(4) == 5
    assert Class.method.would_hit(4)
