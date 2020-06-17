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

::

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

Customization
-------------

`cache_decor` is flexible because it supports multiple backends.

1. `MemoryStore`: backed in RAM for the duration of the program

2. `FileStore`: backed in an index file which is loaded on first call.

3. `DirectoryStore`: backed in a directory. Results are stored as
   individual files in that directory, and they are loaded lazily. Use
   this for functions that return large objects.

4. Custom stores: to create a custom store, just extend `ObjectStore`
   and implement a dict-like interface.

`FileStore` and `DirectoryStore` can both themselves be customized by:

- Providing a `cache_path`  (conforming to the `PathLike` interface), e.g. an `S3Path` object.

- Providing a `serializer` (conforming to the `Serializer` interface), e.g. [pickle] (default), [cloudpickle], [dill], [messagepack].

`cache_decor` also takes a "state function" which computes the value
of some external state that this computation should depend on. Unlike
the arguments (which the cache explicitly depends on), values computed
with a different state are evicted out, so this is appropriate when
you never expect to revisit a prior state (e.g. modtime of a file
could be a state, as in `make_file_state_fn`).

CLI
---

::

    # cache a commandline function based on its args
    read n
    cache -- compute_prime ${n}

    # cache based on args AND file-modtime
    # recompiles when main.c is newer than the most recent compile
    cache --file main.c -- gcc main.c -o main
