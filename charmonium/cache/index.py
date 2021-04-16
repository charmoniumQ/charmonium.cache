from __future__ import annotations
import enum
from typing import (
    Optional,
    cast,
    Callable,
    Generic,
    TypeVar,
    Any,
    Iterable,
)


class IndexKeyType(enum.IntEnum):
    MATCH = 0
    LOOKUP = 1


Key = TypeVar("Key")
Val = TypeVar("Val")

class Index(Generic[Key, Val]):
    def __init__(self, schema: tuple[IndexKeyType, ...]) -> None:
        self.schema = schema
        self._data = dict[Key, Any]()

    def items(self) -> Iterable[tuple[tuple[Key, ...], Val]]:
        def helper(data: dict[Key, Any], depth: int) -> Iterable[tuple[tuple[Key, ...], Val]]:
            if depth == 1:
                # depth = 0 would be the actual values
                # data.items() wouldn't work.
                for key, val in data.items():
                    yield ((key,), val)
            else:
                for key, subdict in data.items():
                    for subkey, val in helper(cast(dict[Key, Any], subdict), depth - 1):
                        yield ((key,) + subkey, val)

        yield from helper(self._data, len(self.schema))

    def _get_last_level(self, keys: tuple[Key, ...]) -> Optional[tuple[dict[Key, Val], Key, IndexKeyType]]:
        if len(keys) != len(self.schema):
            raise ValueError(f"{keys=} should be the same len as {self.schema=}")
        obj = self._data
        for key in keys[:-1]:
            if key not in obj:
                return
            obj = cast(dict[Key, Any], obj[key])
        return cast(dict[Key, Val], obj), keys[-1], self.schema[-1]

    def _get_or_create_last_level(self, keys: tuple[Key, ...]) -> tuple[dict[Key, Val], Key, IndexKeyType]:
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
        last_level, last_key, last_key_type = self._get_or_create_last_level(keys)
        if last_key not in last_level:
            if last_key_type == IndexKeyType.MATCH:
                last_level.clear()
            last_level[last_key] = thunk()
        return last_level[last_key]

    def __setitem__(self, keys: tuple[Key, ...], val: Val) -> None:
        last_level, last_key, last_key_type = self._get_or_create_last_level(keys)
        if last_key_type == IndexKeyType.MATCH:
            last_level.clear()
        last_level[last_key] = val

    def __delitem__(self, keys: tuple[Key, ...]) -> None:
        result = self._get_last_level(keys)
        if result:
            last_level, last_key, _ = result
            del last_level[last_key]

    def __getitem__(self, keys: tuple[Key, ...]) -> Val:
        result = self._get_last_level(keys)
        if result:
            last_level, last_key, _ = result
            return last_level[last_key]
        else:
            raise KeyError(keys)

    def __contains__(self, keys: tuple[Key, ...]) -> bool:
        if len(keys) != len(self.schema):
            raise ValueError(f"{keys=} should be the same len as {self.schema=}")
        result = self._get_last_level(keys)
        if result:
            last_level, last_key, _ = result
            return last_key in last_level
        else:
            return False

    def update(self, other: Index[Key, Val]) -> None:
        if other.schema != self.schema:
            raise ValueError(f"Schema mismatch {self.schema=}, {other.schema=}")
        for key, val in other.items():
            self.get_or(key, lambda: val)
