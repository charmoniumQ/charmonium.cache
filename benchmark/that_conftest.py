import os

import pytest
from charmonium.freeze import config as freeze_config
from charmonium.cache import Memoized, MemoizedGroup
from charmonium.cache.util import with_attr

memoization = not bool(os.environ.get("CHARMONIUM_CACHE_DISABLE", True))
print(f"Using {__file__} with memoization = {memoization}")

if memoization:
    freeze_config.recursion_limit = 200
    group = MemoizedGroup(size="4GiB")

    def pytest_itemcollected(item: pytest.Item) -> None:
        print(f"Caching {item!r}")
        item.obj = Memoized(item.obj, group=group)
