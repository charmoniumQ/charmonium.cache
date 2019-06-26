'''
# charmonium.cache

This package provides a decorator that caches a function. It stores
the arguments and the returned object. The next time the function is
called with the same arguments, the result is loaded from the cache
instead of computed.

## Basic usage

    >>> @Cache.decor(MemoryStore.create())
    ... def square(x):
    ...     print('computing')
    ...     return x**2
    ...
    >>> square(4)
    computing
    16
    >>> square(4) # square is not called again; answer is just looked up
    16

## Flexibility

This decorator is flexible because it supports multiple backends.

1. `MemoryStore`: backed in RAM for the duration of the program
2. `FileStore`: backed in an index file which is loaded on first call.
3. `DirectoryStore`: backed in a directory. Results are stored as
   individual files in that directory, and they are loaded lazily. Use
   this for functions that return large objects.
4. Custom stores: to create a custom store, just extend `ObjectStore`
   and implement a dict-like interface.

Another way to customize this is to use `FileStore` or
`DirectoryStore` with an object conforming to the `PathLike`
interface (e.g. Path or something that acts like it).

Another way to customize this is to use `FileStore` or
`DirectoryStore` with an object conforming to the `Serializer`
interface (e.g. pickle, cloudpickle, dill, messagepack).

If you are reading data from external files, consider using
`make_file_state_fn`. It will recompute the entry when the file
changes on the disk.

## CLI usage

    # cache a commandline function based on its args
    read n
    cache -- compute_prime ${n}

    # cache based on args AND file-modtime
    # recompiles when main.c is newer than the most recent compile
    cache --file main.c -- gcc main.c -o main

'''

from .core import (
    Cache, ObjectStore, MemoryStore, FileStore, DirectoryStore, make_file_state_fn
)
version = '0.1.0'
