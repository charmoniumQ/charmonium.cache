import datetime
from typing import Any, Callable, TypeVar

import attr

T = TypeVar("T")


# pyright thinks attrs has ambiguous overload
@attr.define  # type: ignore
class Entry:
    value: Any
    data_size: int
    recompute_time: datetime.timedelta
    time_saved: datetime.timedelta
    obj_store: bool
    last_use: datetime.datetime = datetime.datetime.fromtimestamp(0)
    # last_use_count: int


def luv(entry: Entry) -> float:
    return 0


policies = dict[str, Callable[[Entry], Any]](luv=luv,)
