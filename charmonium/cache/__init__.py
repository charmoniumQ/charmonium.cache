from .helpers import FileContents as FileContents, TTLInterval as TTLInterval
from .memoize import (
    DEFAULT_MEMOIZED_GROUP as DEFAULT_MEMOIZED_GROUP,
    Memoized as Memoized,
    MemoizedGroup as MemoizedGroup,
    __version__ as __version__,
    memoize as memoize,
)
from .obj_store import DirObjStore as DirObjStore, ObjStore as ObjStore
from .pathlike import PathLike as PathLike, pathlike_from as pathlike_from
from .pickler import Pickler as Pickler
from .replacement_policies import (
    GDSize as GDSize,
    ReplacementPolicy as ReplacementPolicy,
)
from .rw_lock import (
    FileRWLock as FileRWLock,
    Lock as Lock,
    NaiveRWLock as NaiveRWLock,
    RWLock as RWLock,
)
from .util import Future as Future, with_attr as with_attr

import logger
perf_logger_file = os.environ.get("CHARMONIUM_CACHE_PERF_LOG")
if perf_logger_file:
    perf_logger = logging.getLogger("charmonium.cache.perf")
    perf_logger.setLevel(logging.DEBUG)
    perf_logger.addHandler(logging.FileHandler(perf_logger_file))
    perf_logger.propagate = False

__author__ = "Samuel Grayson"
__email__ = "sam+dev@samgrayson.me"
__license__ = "MPL-2.0"
__copyright__ = "2020 Samuel Grayson"
