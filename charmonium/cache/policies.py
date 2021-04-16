from typing import Callable, TypeVar, Any
import datetime

import attr

T = TypeVar("T")


@attr.define  # type: ignore (pyright: attrs ambiguous overload)
class Entry:
    value: Any
    data_size: int
    recompute_time: datetime.timedelta
    time_saved: datetime.timedelta
    obj_store: bool
    last_use: datetime.datetime = datetime.datetime.fromtimestamp(0)
    # last_use_count: int


def LUV(entry: Entry) -> float:
    return 0


policies = dict[str, Callable[[Entry], Any]](LUV=LUV,)
