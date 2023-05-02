import copy
import logging

import charmonium.time_block as ch_time_block

from charmonium.cache import DEFAULT_FREEZE_CONFIG, MemoizedGroup, DirObjStore, memoize
from charmonium.cache.util import temp_path


def test() -> None:
    freeze_config = copy.deepcopy(DEFAULT_FREEZE_CONFIG)
    freeze_config.recursion_limit = 30
    # In general, asyncio.current_task is going to inject non-cache-safe data.
    # But in our case, we know that the data will not be used in a way that affects the output.
    # So we ask freeze to ignore this function.
    freeze_config.ignore_classes.update(
        {
            ("charmonium.time_block.time_block", "TimeBlock"),
        }
    )
    freeze_config.ignore_objects_by_class.update(
        {
            ("charmonium.time_block.time_block", "TimeBlock"),
        }
    )
    freeze_config.ignore_functions.update(
        {
            ("charmonium.time_block.time_block", "ctx"),
        }
    )

    @ch_time_block.decor()
    @memoize(group=MemoizedGroup(
        obj_store=DirObjStore(temp_path()),
        freeze_config=freeze_config,
        temporary=True,
    ))
    @ch_time_block.decor()
    def square(x: int) -> int:
        return x**2

    assert square(3) == 9
