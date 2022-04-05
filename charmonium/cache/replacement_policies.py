from __future__ import annotations

import abc
import datetime
from typing import TYPE_CHECKING, Any, Mapping

import attr
import bitmath


# pyright thinks attrs has ambiguous overload
@attr.define  # type: ignore
class Entry:
    value: Any
    data_size: bitmath.Bitmath
    function_time: datetime.timedelta
    serialization_time: datetime.timedelta
    obj_store: bool


# TODO: test that these methods are called at the right time.
class ReplacementPolicy:  # pylint: disable=no-self-use,unused-argument
    """A replacement policy for a cache"""

    @abc.abstractmethod
    def add(self, key: Any, entry: Entry) -> None:
        """Called when a key, entry pair is added to the index."""

    @abc.abstractmethod
    def access(self, key: Any, entry: Entry) -> None:
        """Called when a key, entry pair is accessed/used.

        Update last-used-time here.
        """

    def invalidate(self, key: Any, entry: Entry) -> None:
        """Called when a key is invalidated by the a subkey-to-match.

        This could be useful as a metric to see develop a heuristic
        for fast a versioned resources is changing.

        """

    @abc.abstractmethod
    def evict(self) -> tuple[Any, Entry]:
        """Select a key, entry pair to evict."""

    @abc.abstractmethod
    def update(self, other: ReplacementPolicy) -> None:
        """Update self with contents of other, but self overrides other.

        This is necessary because there could be multiple processes
        using the same MemoizedGroup. A differnet process may have
        made progress. We want to incorporate their progress into this
        process.

        """


class GDSize(ReplacementPolicy):
    """GreedyDual-Size policy, described by [Cao et al]_."""

    def __init__(self) -> None:
        self.inflation = 0.0
        self._data: dict[Any, tuple[float, Entry]] = {}

    def add(self, key: Any, entry: Entry) -> None:
        self.access(key, entry)

    def access(self, key: Any, entry: Entry) -> None:
        score = self.inflation + (
            entry.function_time + entry.serialization_time
        ).total_seconds() / max(entry.data_size.to_Byte().value, 1)
        self._data[key] = (score, entry)

    def invalidate(
        self, key: Any, entry: Any
    ) -> None:  # pylint: disable=unused-argument
        del self._data[key]

    def evict(self) -> tuple[Any, Entry]:
        if self._data:
            self.inflation, key, entry = min(
                [(score, key, entry) for key, (score, entry) in self._data.items()]
            )
            del self._data[key]
            return key, entry
        else:
            raise ValueError("No data left to evict")

    def update(self, other: ReplacementPolicy) -> None:
        if isinstance(other, GDSize) or (
            type(other).__name__ == type(self).__name__ and not TYPE_CHECKING
        ):
            # I need the type(other).__name == type(self).__name__ because when this class is de/serialized, Python forgets that it is equal.
            # However, I don't want the type checker to think too hard about it; it should just know isinstance(other, GDSIze), so I add not TYPE_CHECKING.
            self._data.update(other._data)  # pylint: disable=protected-access
            self.inflation = other.inflation
        else:
            raise TypeError(f"Cannot update a {type(self)} from a {type(other)}")


REPLACEMENT_POLICIES: Mapping[str, type[ReplacementPolicy]] = dict(
    gdsize=GDSize,
)
