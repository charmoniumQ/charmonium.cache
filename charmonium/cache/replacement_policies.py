from __future__ import annotations

import abc
import datetime
from typing import TYPE_CHECKING, Any

import attr
import bitmath


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
class GDSize(ReplacementPolicy):
    """GreedyDual-Size policy, described by [Cao et al.]_.

    .. [Cao et al.] Cao, Pei, and Sandy Irani. "Cost-aware www proxy caching algorithms." _Usenix symposium on internet technologies and systems_. Vol. 12. No. 97. 1997. https://www.usenix.org/legacy/publications/library/proceedings/usits97/full_papers/cao/cao.pdf

    """
    def __init__(self) -> None:
        self.inflation = 0.0
        self._data = dict[Any, float]()
    def add(self, key: Any, entry: Entry) -> None:
        self.access(key, entry)
    def access(self, key: Any, entry: Entry) -> None:
        self._data[key] = self.inflation + entry.recompute_time.total_seconds() / entry.data_size.to_KiB().value
    def invalidate(self, key: Any, entry: Any) -> None: # pylint: disable=unused-argument
        del self._data[key]
    def evict(self) -> tuple[Any, Entry]:
        if self._data:
            self.inflation, key = min([(score, key) for key, score in self._data.items()])
            return key
        else:
            raise ValueError("No data left to evict")
    def update(self, other: ReplacementPolicy) -> None:
        if isinstance(other, GDSize) or (type(other).__name__ == type(self).__name__ and not TYPE_CHECKING):
            # I need the type(other).__name == type(self).__name__ because when this class is de/serialized, Python forgets that it is equal.
            # However, I don't want the type checker to think too hard about it; it should just know isinstance(other, GDSIze), so I add not TYPE_CHECKING.
            self._data.update(other._data) # pylint: disable=protected-access
            self.inflation = other.inflation
        else:
            raise TypeError(f"Cannot update a {type(self)} from a {type(other)}")

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
        if isinstance(other, Dummy) or (type(other).__name__ == type(self).__name__ and not TYPE_CHECKING):
            self._data.update(other._data) # pylint: disable=protected-access
        else:
            raise TypeError(f"Cannot update a {type(self)} from a {type(other)}")

REPLACEMENT_POLICIES = dict[str, type[ReplacementPolicy]](
    gdsize=GDSize,
    dummy=Dummy,
)
