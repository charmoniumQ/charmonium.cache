import logging

import charmonium.time_block as ch_time_block

from charmonium.cache import freeze_config, memoize


def test() -> None:
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
    @memoize()
    @ch_time_block.decor()
    def square(x: int) -> int:
        return x**2

    assert square(3) == 9
