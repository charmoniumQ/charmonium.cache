=============
API Reference
=============

.. autosummary::


.. automodule:: charmonium.cache

Core
----

    .. autodecorator:: memoize

    .. autoclass:: Memoized
        :members:
        :special-members: __init__

    .. autoclass:: MemoizedGroup
        :members:
        :special-members: __init__

Components
----------

    .. autoclass:: ObjStore
        :members:
        :special-members: __getitem__, __setitem__, __delitem__, __hash__

    .. autoclass:: DirObjStore
        :members:
        :special-members: __init__

    .. autoclass:: ReplacementPolicy
        :members:
        :special-members: __init__

    .. autoclass:: GDSize
        :members:

    .. autoclass:: Pickler
        :members:

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

Helpers
-------

    .. autoclass:: FileContents
        :members:
        :special-members: __init__, __cache_key__, __cache_val__

    .. autoclass:: TTLInterval
        :members:
        :special-members: __init__

Utils
-----

    .. autoclass:: PathLike
        :members:
        :special-members: __truediv__

    .. autoclass:: Future
        :members:
        :special-members: __init__

    .. autofunction:: determ_hash

    .. autofunction:: hashable
