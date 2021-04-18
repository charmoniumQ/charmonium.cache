=============
API Reference
=============

.. autosummary::


.. automodule:: charmonium.cache

    .. autodecorator:: memoize

    .. autoclass:: MemoizedGroup
        :members:
        :special-members: __init__

    .. autoclass:: ObjStore
        :members:
        :special-members: __getitem__, __setitem__, __delitem__, __hash__

    .. autoclass:: DirObjStore
        :members:
        :special-members: __init__

    .. autoclass:: ReplacementPolicy
        :members:
        :special-members: __init__

    .. autoclass:: FileContents
        :members:
        :special-members: __init__, __cache_key__, __cache_val__

    .. autoclass:: RWLock
        :members:

    .. autoclass:: FileRWLock
        :members:
        :special-members: __init__

    .. autoclass:: NaiveRWLock
        :members:
        :special-members: __init__

    .. autoclass:: Lock
        :members:

    .. autoclass:: KeyGen
        :members:
        :special-members: __init__, __next__

    .. autoclass:: Future
        :members:
        :special-members: __init__

    .. autoclass:: PathLike
        :members:
        :special-members: __truediv__
