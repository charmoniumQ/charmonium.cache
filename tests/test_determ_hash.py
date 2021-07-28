from __future__ import annotations

import copy
import pickle
from pathlib import Path
from typing import Any, Hashable, List, TypeVar

import numpy
import pytest

from charmonium.cache.determ_hash import determ_hash, hashable

def insert_recurrence(lst: List[Any], idx: int) -> List[Any]:
    lst = lst.copy()
    lst.insert(idx, lst)
    return lst

class WithDetermHash:
    def __init__(self, x: int) -> None:
        self.x = x
    def __determ_hash__(self) -> Any:
        return self.x
    def __eq__(self, other: object) -> bool:
        return self.x == getattr(other, "x", None)


class WithProperties:
    def __init__(self, x: int) -> None:
        self._x = x
    @property
    def x(self) -> int:
        return self._x
    @x.setter
    def x(self, new_x) -> None:
        pass
    @x.deleter
    def x(self) -> None:
        pass
    def __eq__(self, other: object) -> bool:
        return self.x == getattr(other, "x", None)

class WithSlots:
    __slots__ = ["x"]
    def __init__(self, x: int) -> None:
        self.x = x
    def __eq__(self, other: object) -> bool:
        return self.x == getattr(other, "x", None)

class WithSuper(WithProperties):
    def __init__(self, x: int) -> None:
        super().__init__(x)
    def __eq__(self, other: object) -> bool:
        return self.x == getattr(other, "x", None)

def create_non_picklable_obj(x: int) -> Any:
    class NotTopLevel:
        def __init__(self, x: int):
            self.x = x
        def __eq__(self, other: object) -> bool:
            return self.x == getattr(other, "x", None)

    return NotTopLevel(x)

determ_hashables: [str, List[Hashable]] = {
    "none": [None],
    "bytes": [b"hello", b"world"],
    "str": ["hello", "world"],
    "int": [123, 456, -123],
    "float": [2.0, 2.1],
    "complex": [3+1j, 3+2j],
    "tuple": [((1, 2), 3), ((1, 2), 4)],
    "Path obj": [Path(), Path("abc"), Path("def")],
    "obj with __determ_hash__": [WithDetermHash(3), WithDetermHash(4)],
}

non_hashables: [str, List[Any]] = {
    "recursive_list": [insert_recurrence([1, 2, 3, 4], 2), insert_recurrence([1, 2, 3, 5], 2)],
    "module": [pickle, numpy],
    "bytearray": [bytearray(b"hello"), bytearray(b"world")],
    "frozenset": [frozenset({1, 2, 3}), frozenset({3, 4, 5})],
    "dict of dicts": [dict(a=1, b=2, c=3), dict(a=1, b=2, c=4)],
    "set": [{1, 2, 3}, {1, 2, 4}],
    "function": [create_non_picklable_obj, insert_recurrence],
    "bare method": [WithSuper.__init__, WithSlots.__init__],
    "bound method": [WithDetermHash(3).__eq__, WithDetermHash(4).__eq__],
    "class": [WithDetermHash, WithProperties, WithSlots],
    "obj with __determ_hash__": [WithDetermHash(3), WithDetermHash(4)],
    "obj with properties": [WithProperties(3), WithProperties(4)],
    "obj with slots": [WithSlots(3), WithSlots(4)],
    "obj with super": [WithSuper(3), WithSuper(4)],
    "nonpicklable obj": [create_non_picklable_obj(3), create_non_picklable_obj(4)],
    "numpy array": [numpy.zeros(4), numpy.ones(4)],
    "lambdas": [lambda: 1, lambda: 2],
    "builtin_functions": [open, zip],
    "builtin_types": [type, property, memoryview],
    "numpy numbers": [numpy.int64(123), numpy.int64(456), numpy.float32(3.2), numpy.float32(3.3)]
}

non_hashable_equivalences: [str, List[Any]] = {
    "recursive_list": [insert_recurrence([1, 2, 3, 4], 2), insert_recurrence([1, 2, 3, 4], 2)],
    "lambda": [lambda: 1, lambda: 1],
    "bound method": [WithDetermHash(3).__eq__, WithDetermHash(3).__eq__],
    "numpy array": [numpy.zeros(4), numpy.zeros(4)],
}


T = TypeVar("T")
def unique(it: Iterable[T]) -> bool:
    lst = list(it)
    return len(set(lst)) == len(lst)


@pytest.mark.parametrize("input_kind", non_hashables.keys())
def test_make_hashable(input_kind: str) -> None:
    inputs = non_hashables[input_kind]
    # hashable part is unique
    assert unique(hash(hashable(input)) for input in inputs)

    for input in inputs:
        # but hashable part is also stable across copies
        assert hash(hashable(input)) == hash(hashable(copy.deepcopy(input)))

        if input_kind not in determ_hashables:
            with pytest.raises(TypeError):
                determ_hash(input)

@pytest.mark.parametrize("input_kind", non_hashable_equivalences.keys())
def test_make_hashable_equivalences(input_kind: str) -> None:
    inputs = non_hashable_equivalences[input_kind]
    assert len(set(hash(hashable(input)) for input in inputs)) == 1

@pytest.mark.parametrize("input_kind", determ_hashables.keys())
def test_determ_hash(input_kind: str) -> None:
    inputs = determ_hashables[input_kind]
    assert unique(determ_hashable(input) for input in inputs)
    for input in inputs:
        assert determ_hash(input) == determ_hash(copy.deepcopy(input))

def test_determ_hash_persistence() -> None:
    expected = 0
    p = determ_hash(frozenset(determ_hashables.items()))
    assert (
        p == expected
    ), f"If you changed how persistent hash works, just change the `expected` to {p}."


def test_closure() -> None:
    i = 0

    def func():
        return i

    func1 = hashable(func)
    i = 1
    func2 = hashable(func)
    assert func1 != func2, "Change in closure should change hash"
