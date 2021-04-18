import bitmath
import datetime
from typing import Any

import attr


# pyright thinks attrs has ambiguous overload
@attr.define  # type: ignore
class Entry:
    value: Any
    data_size: bitmath.Bitmath
    recompute_time: datetime.timedelta
    time_saved: datetime.timedelta
    obj_store: bool
    last_use: datetime.datetime = datetime.datetime.fromtimestamp(0)
    # last_use_count: int


class ReplacementPolicy:
    def add(self, key: Any, entry: Entry) -> None:
        ...
    def access(self, key: Any, entry: Entry) -> None:
        ...
    def evict(self) -> tuple[Any, Entry]:
        ...

    # TODO: this
class LUV(ReplacementPolicy):
    ...


class GDSize(ReplacementPolicy):
    ...

class Dummy(ReplacementPolicy):
    def __init__(self) -> None:
        self._data: list[tuple[Any, Entry]] = []
    def add(self, key: Any, entry: Entry) -> None:
        self._data.append((key, entry))
    def access(self, key: Any, entry: Entry) -> None:
        pass
    def evict(self) -> tuple[Any, Entry]:
        return self._data.pop(-1)

REPLACEMENT_POLICIES = dict[str, type[ReplacementPolicy]](
    luv=LUV,
    gdsize=GDSize,
    dummy=Dummy,
)
