================
charmonium.cache
================

Provides a decorator for caching a function and an equivalent
command-line util.

It wraps an ordinary function. Whenever the function is called with
the same arguments, the result is loaded from the cache instead of
computed.

Quickstart
----------

::

    $ pip install charmonium.cache

.. code:: python

    >>> import charmonium.cache as ch_cache
    >>> @ch_cache.decor(ch_cache.MemoryStore.create())
    ... def square(x):
    ...     print('computing')
    ...     return x**2
    ...
    >>> square(4)
    computing
    16
    >>> square(4) # square is not called again; answer is just looked up
    16
    >>> with square.disabled():
    ...     # disable caching; always recomptue
    ...     square(4)
    ...
    computing
    16

Customization
-------------

``cache_decor`` is flexible because it supports multiple backends.

1. ``MemoryStore``: backed in RAM for the duration of the program (see
   example above).

2. ``FileStore``: backed in a file which is loaded on first call.

.. code:: python

    >>> import charmonium.cache as ch_cache
    >>> @ch_cache.decor(ch_cache.FileStore.create("tmp/1"))
    ... def square(x):
    ...     return x**2
    ...
    >>> # Now that we cache in a file, this is persistent between runs
    >>> # So I must clear it here.
    >>> square.clear()
    >>> list(map(square, range(5)))
    [0, 1, 4, 9, 16]
    >>> import os
    >>> os.listdir("tmp/1")
    ['__main__.square_cache.pickle']

3. ``DirectoryStore``: backed in a directory. Results are stored as
   individual files in that directory, and they are loaded lazily. Use
   this for functions that return large objects.

.. code:: python

    >>> import charmonium.cache as ch_cache
    >>> @ch_cache.decor(ch_cache.DirectoryStore.create("tmp/2"))
    ... def square(x):
    ...     return x**2
    ...
    >>> # Now that we cache in a file, this is persistent between runs
    >>> # So I must clear it here.
    >>> square.clear()
    >>> list(map(square, range(5)))
    [0, 1, 4, 9, 16]
    >>> import os
    >>> sorted(os.listdir("tmp/2/__main__.square"))
    ['(0).pickle', '(1).pickle', '(2).pickle', '(3).pickle', '(4).pickle']

4. Custom stores: to create a custom store, just extend ``ObjectStore``
   and implement a dict-like interface.

``FileStore`` and ``DirectoryStore`` can both themselves be customized by:

- Providing a ``cache_path`` (conforming to the ``PathLike`` interface),
  e.g. one can transparently cache in AWS S3 with an `S3Path`_ object.

.. _`S3Path`: https://pypi.org/project/s3path/

- Providing a ``serializer`` (conforming to the ``Serializer`` interface),
  e.g. `pickle`_ (default), `cloudpickle`_, `dill`_, or `messagepack`_.

.. _`pickle`: https://docs.python.org/3/library/pickle.html
.. _`cloudpickle`: https://github.com/cloudpipe/cloudpickle
.. _`dill`: https://github.com/uqfoundation/dill
.. _`messagepack`: https://github.com/msgpack/msgpack-python

``cache_decor`` also takes a "state function" which computes the value
of some external state that this computation should depend on. Unlike
the arguments (which the cache explicitly depends on), values computed
with a different state are evicted out, so this is appropriate when
you never expect to revisit a prior state (e.g. modtime of a file
could be a state, as in ``make_file_state_fn``).

With ``verbose=True``, this will output to a logger.

.. code:: python

    >>> import charmonium.cache as ch_cache
    >>> @ch_cache.decor(ch_cache.MemoryStore.create(), verbose=True)
    ... def square(x):
    ...     print('computing')
    ...     return x**2
    ...
    >>> square(4) # doctest:+SKIP
    2020-06-19 11:31:40,197 - __main__.square: miss with args: (4,), {}
    computing
    16
    >>> square(4) # doctest:+SKIP
    2020-06-19 11:31:40,197 - __main__.square: hit with args: (4,), {}
    16

CLI
---

::

    # cache a commandline function based on its args
    $ cache --verbose -- compute_square 6
    miss for square(["6"])
    36

    $ cache -- compute_square 6
    hit for square(["6"])
    36
