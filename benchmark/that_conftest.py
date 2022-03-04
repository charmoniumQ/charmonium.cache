import pytest
from charmonium.freeze import config as freeze_config
from charmonium.cache import Memoized, MemoizedGroup
from charmonium.cache.util import with_attr

group = MemoizedGroup(size="4GiB")

print("Using that_conftest.py")

freeze_config.recursion_limit = 200

def pytest_itemcollected(item: pytest.Item) -> None:
    print(f"Caching {item!r}")
    item.obj = Memoized(item.obj, group=group)
