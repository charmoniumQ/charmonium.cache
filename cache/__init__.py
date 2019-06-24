'''
# Caching decorator

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

'''

from .cache import Cache, ObjectStore, MemoryStore, FileStore, DirectoryStore
