from typing import Callable, TypeVar, Any
import datetime

import attr

T = TypeVar("T")


@attr.s  # type: ignore (pyright: attrs ambiguous overload)
class Entry:
    data_size: int
    compute_time: float
    obj_store: bool
    last_use: datetime.datetime
    value: Any


def LUV(entry: Entry) -> float:
    return 0


policies = dict[str, Callable[[Entry], Any]](LUV=LUV,)
