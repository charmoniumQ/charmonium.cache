from __future__ import annotations

import abc
import datetime
from typing import Any

import attr
import bitmath

from .util import GetAttr


# pyright thinks attrs has ambiguous overload
@attr.define  # type: ignore
class Entry:
    value: Any
    data_size: bitmath.Bitmath
    recompute_time: datetime.timedelta
    time_saved: datetime.timedelta
    obj_store: bool


# TODO: test that these methods are called at the right time.
class ReplacementPolicy:  # pylint: disable=no-self-use,unused-argument
    @abc.abstractmethod
    def add(self, key: Any, entry: Entry) -> None:
        ...
    @abc.abstractmethod
    def access(self, key: Any, entry: Entry) -> None:
        ...
    def invalidate(self, key: Any, entry: Entry) -> None:
        ...
    @abc.abstractmethod
    def evict(self) -> tuple[Any, Entry]:
        ...
    @abc.abstractmethod
    def update(self, other: ReplacementPolicy) -> None:
        # TODO: Unlike dict update, self overrides other
        ...


# TODO: implement other replacement policies

class Dummy(ReplacementPolicy):  # pylint: disable=no-self-use,unused-argument
    def __init__(self) -> None:
        self._data = dict[Any, Entry]()
    def add(self, key: Any, entry: Entry) -> None:
        self._data[key] = entry
    def access(self, key: Any, entry: Entry) -> None:
        pass
    def invalidate(self, key: Any, entry: Any) -> None:
        del self._data[key]
    def evict(self) -> tuple[Any, Entry]:
        if self._data:
            return next(iter(self._data.items()))
        else:
            raise ValueError("No data left to evict")
    def update(self, other: ReplacementPolicy) -> None:
        if type(other).__name__ == "Dummy":
            # Python doesn't know that charmonium.cache.ReplacementPolicies.Dummy == cache.ReplacementPolicies.Dummy
            # due to the relative import.
            for key, val in GetAttr[dict[Any, Entry]]()(other, "_data", check_callable=False).items():
                if key not in self._data:
                    self._data[key] = val
        else:
            raise TypeError(f"Cannot update a Dummy ReplacementPolicy from a {type(other)} {type(self)}")

REPLACEMENT_POLICIES = dict[str, type[ReplacementPolicy]](
    dummy=Dummy,
)
