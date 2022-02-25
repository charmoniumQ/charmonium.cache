import charmonium.time_block as ch_time_block
from charmonium.cache import memoize

def test():
    @ch_time_block.decor()
    @memoize()
    @ch_time_block.decor()
    def foo():
        pass

    foo()
