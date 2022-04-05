from __future__ import annotations

import enum
from typing import Any, Callable, Dict, Generic, Iterable, Optional, TypeVar, cast


class IndexKeyType(enum.IntEnum):
    MATCH = 0
    LOOKUP = 1


Key = TypeVar("Key")
Val = TypeVar("Val")


class Index(Generic[Key, Val]):
    def __init__(
        self,
        schema: tuple[IndexKeyType, ...],
        deleter: Optional[Callable[[tuple[tuple[Key, ...], Val]], None]] = None,
    ) -> None:
        self.schema = schema
        self._data: dict[Key, Any] = {}
        self._deleter = deleter

    def __getstate__(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "_data": self._data,
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.schema = state["schema"]
        self._data = state["_data"]

    @staticmethod
    def _items(
        data: dict[Key, Any], keys: tuple[Key, ...], max_depth: int
    ) -> Iterable[tuple[tuple[Key, ...], Val]]:
        # print("_items", keys, data)
        if len(keys) == max_depth:
            yield (keys, cast(Val, data))
        else:
            for key, subdict in data.items():
                yield from Index._items(
                    cast(Dict[Key, Any], subdict), keys + (key,), max_depth
                )

    def items(self) -> Iterable[tuple[tuple[Key, ...], Val]]:
        yield from self._items(self._data, (), len(self.schema))

    def _delete(self, data: dict[Key, Any], keys: tuple[Key, ...]) -> None:
        if self._deleter:
            for item in self._items(data, keys, len(self.schema)):
                self._deleter(item)
        data.clear()

    def _get_last_level(
        self, keys: tuple[Key, ...]
    ) -> Optional[tuple[dict[Key, Val], Key, IndexKeyType]]:
        if len(keys) != len(self.schema):
            raise ValueError(
                f"Keys {keys} should be the same len as schema ({len(self.schema)})"
            )
        obj = self._data
        for key in keys[:-1]:
            if key not in obj:
                return None
            obj = cast(Dict[Key, Any], obj[key])
        return cast(Dict[Key, Val], obj), keys[-1], self.schema[-1]

    def _get_or_create_last_level(
        self,
        keys: tuple[Key, ...],
    ) -> tuple[dict[Key, Val], Key, IndexKeyType]:
        if len(keys) != len(self.schema):
            raise ValueError(
                f"Keys {keys} should be the same len as schema ({len(self.schema)})"
            )
        obj = self._data
        completed_keys: tuple[Key, ...] = ()
        for key_type, key in zip(self.schema[:-1], keys[:-1]):
            assert key_type != IndexKeyType.MATCH or len(obj) < 2
            if key not in obj:
                if key_type == IndexKeyType.MATCH:
                    self._delete(obj, completed_keys)
                obj[key] = cast(Dict[Key, Any], {})
            completed_keys += (key,)
            obj = cast(Dict[Key, Any], obj[key])
        return cast(Dict[Key, Val], obj), keys[-1], self.schema[-1]

    # TODO: refactor for less complexity
    # Maybe combine get_or_create with get

    def get_or(self, keys: tuple[Key, ...], thunk: Callable[[], Val]) -> Val:
        last_level, last_key, last_key_type = self._get_or_create_last_level(keys)
        if last_key not in last_level:
            if last_key_type == IndexKeyType.MATCH:
                self._delete(last_level, keys[:-1])
            last_level[last_key] = thunk()
        return last_level[last_key]

    def __setitem__(self, keys: tuple[Key, ...], val: Val) -> None:
        last_level, last_key, last_key_type = self._get_or_create_last_level(keys)
        if last_key_type == IndexKeyType.MATCH:
            self._delete(last_level, keys[:-1])
        last_level[last_key] = val

    def __delitem__(self, keys: tuple[Key, ...]) -> None:
        result = self._get_last_level(keys)
        if result:
            last_level, last_key, _ = result
            if last_key in last_level:
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
            raise ValueError(
                f"Keys {keys} should be the same len as schema ({len(self.schema)})"
            )
        result = self._get_last_level(keys)
        if result:
            last_level, last_key, _ = result
            return last_key in last_level
        else:
            return False

    def update(self, other: Index[Key, Val]) -> None:
        if other.schema != self.schema:
            raise ValueError(f"Schema mismatch {self.schema} != {other.schema}")
        for key, val in other.items():
            if key not in self:
                self[key] = val
