from __future__ import annotations
import enum
from typing import (
    cast,
    Callable,
    Generic,
    TypeVar,
    Any,
    Iterable,
)

from .util import Sizeable


class IndexKeyType(enum.IntEnum):
    MATCH = 0
    LOOKUP = 1


Key = TypeVar("Key")
Val = TypeVar("Val")

class Index(Sizeable, Generic[Key, Val]):
    def __init__(self, schema: tuple[IndexKeyType, ...]) -> None:
        self.schema = schema
        self._data = dict[Key, Any]()

    def _get_last_level(self, keys: tuple[Key, ...]) -> tuple[dict[Key, Val], Key, IndexKeyType]:
        if len(keys) != len(self.schema):
            raise ValueError(f"{keys=} should be the same len as {self.schema=}")
        obj = self._data
        for key_type, key in zip(self.schema[:-1], keys[:-1]):
            if key not in obj:
                if key_type == IndexKeyType.MATCH:
                    obj.clear()
                obj[key] = dict[Key, Any]()
            obj = cast(dict[Key, Any], obj[key])
        return cast(dict[Key, Val], obj), keys[-1], self.schema[-1]

    def get_or(self, keys: tuple[Key, ...], thunk: Callable[[], Val]) -> Val:
        last_level, last_key, last_key_type = self._get_last_level(keys)
        if last_key not in last_level:
            if last_key_type == IndexKeyType.MATCH:
                last_level.clear()
            last_level[last_key] = thunk()
        return last_level[last_key]

    def __delitem__(self, keys: tuple[Key, ...]) -> None:
        last_level, last_key, _ = self._get_last_level(keys)
        del last_level[last_key]

    def __setitem__(self, keys: tuple[Key, ...], val: Val) -> None:
        last_level, last_key, last_key_type = self._get_last_level(keys)
        if last_key_type == IndexKeyType.MATCH:
            last_level.clear()
        last_level[last_key] = val

    def __getitem__(self, keys: tuple[Key, ...]) -> Val:
        last_level, last_key, _ = self._get_last_level(keys)
        return last_level[last_key]

    def items(self) -> Iterable[tuple[tuple[Key, ...], Val]]:
        def helper(data: dict[Key, Any], depth: int) -> Iterable[tuple[tuple[Key, ...], Val]]:
            if depth == 1:
                for key, val in data.items():
                    yield ((key,), val)
            else:
                for key, subdict in data.items():
                    for subkey, val in helper(cast(dict[Key, Any], subdict), depth - 1):
                        yield ((key,) + subkey, val)

        yield from helper(self._data, len(self.schema))
