from typing import Callable, TypeVar, Generic, Any
import datetime

import attr

T = TypeVar("T")


@attr.s  # type: ignore
class Entry(Generic[T]):
    data_size: int
    compute_time: float
    obj_store: bool
    last_use: datetime.datetime
    value: T


def LUV(entry: Entry[Any]) -> float:
    return 0


policies = dict[str, Callable[[Entry[Any]], Any]](
    LUV=LUV,
)
