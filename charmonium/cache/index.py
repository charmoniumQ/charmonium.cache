from __future__ import annotations

import enum
from typing import Any, Callable, Generic, Iterable, Optional, TypeVar, cast


class IndexKeyType(enum.IntEnum):
    MATCH = 0
    LOOKUP = 1


Key = TypeVar("Key")
Val = TypeVar("Val")


class Index(Generic[Key, Val]):
    def __init__(self, schema: tuple[IndexKeyType, ...], deleter: Optional[Callable[[tuple[tuple[Key, ...], Val]], None]] = None) -> None:
        self.schema = schema
        self._data = dict[Key, Any]()
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
    def _items(data: dict[Key, Any], keys: tuple[Key, ...], max_depth: int) -> Iterable[tuple[tuple[Key, ...], Val]]:
        if len(keys) == max_depth:
            yield (keys, cast(Val, data))
        else:
            for key, subdict in data.items():
                yield from Index._items(cast(dict[Key, Any], subdict), keys + (key,), max_depth)

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
            raise ValueError(f"{keys=} should be the same len as {self.schema=}")
        obj = self._data
        for key in keys[:-1]:
            if key not in obj:
                return None
            obj = cast(dict[Key, Any], obj[key])
        return cast(dict[Key, Val], obj), keys[-1], self.schema[-1]

    def _get_or_create_last_level(
            self, keys: tuple[Key, ...],
    ) -> tuple[dict[Key, Val], Key, IndexKeyType]:
        if len(keys) != len(self.schema):
            raise ValueError(f"{keys=} should be the same len as {self.schema=}")
        obj = self._data
        completed_keys: tuple[Key, ...] = ()
        for key_type, key in zip(self.schema[:-1], keys[:-1]):
            if key not in obj:
                if key_type == IndexKeyType.MATCH:
                    self._delete(obj, completed_keys)
                obj[key] = dict[Key, Any]()
            obj = cast(dict[Key, Any], obj[key])
            completed_keys += (key,)
        return cast(dict[Key, Val], obj), keys[-1], self.schema[-1]

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
            # this lambda confuses pyright, hence type ignore
            self.get_or(key, lambda val=val: val)  # type: ignore
