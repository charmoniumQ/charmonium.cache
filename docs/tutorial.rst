Tutorial
========

Cache Internals
---------------

The cache is organized into an *index* and an *object-store*. The index maps *keys* to
*entries*. Each entry (usually) holds an *object key* that maps to an *object* in the object
store. The *object* is the serialized return value of the function.

The key is a tuple of *subkeys*. The index is hierarchical on each subkey (a dict of dict of dicts
etc.). Each subkey is either a *lookup* or *match* subkey. If a *lookup* subkey is not found, the
subkey is inserted beside the non-matching subkeys. If a *match* subkey is not found, the subkey
replaces the old subkey. This replacing behavior makes sense when there should only be one active
"version" of a certain key. For example, the source code of the function is a match subkey, because
we don't need to store entries for old versions of the source; if the source changes, we should dump
the old entries.

The key has five subkeys:

1. The state of the system (match): this includes the package version
2. The function name (lookup)
3. The function version (match): this includes the source-code, closure-state, and memoization configuration
4. The arguments (lookup)
5. The argument versions (match): this is user-defined and could be the modtime of a file.

How to Use
----------

First you need to identify candidates for memoization.

- They should be *mostly* `pure`_. The library is correct in the presence of global variables, if
  they change frequently, it will degrade performance.

- Likewise, The function and those it depends on should be relatively stable.

- The function should have a high rate of reused arguments.

- The returned value should have a low data storage size. You can customize the returned object with
  |__getstate__|_.

- The function should have a long compute time, so memoization can save a lot of work.

Then you simply add ``@memoize()`` to the line above the function definition. Per-function
customizations go inside the parens. For example,

    .. code:: python
    >>> @memoize()
    >>> def square(x):
    ...     print(f"squaring {x}")
    ...     return x**2
    ... 
    >>> square(2)
    squaring 2
    4
    >>> square(2)
    4

Capturing Filesystem Side-Effects
---------------------------------

Sadly, not all code is pure; many times, legacy code has impure side effects on the filesystem. To
make legacy code memoizable, the library has a |FileContents|_ helper. This class represents a
filepath **and its contents**. Suppose we have the following impure function:

.. code:: python

    def copy(src: str) -> None:
        with open(src, "rb") as src_f:
            result = long_function(src_f.read())
        with open(src + "_copy", "wb") as dst_f:
            dst_f.write(result)

We can convert this to a pure function by:

.. code:: python

    @memoize()
    def pure_copy(src: FileContents, dst: str) -> FileContents:
        copy(src, dst)
        return dst

This can be cached. If you give a ``src`` with the same path and same contents, then the output will
be recalled instead of computed (``long_function`` need not be called).

Note that if the function is called with the same path but different contents, the function will be
recomputed and the "old version" of the output will be **replaced** with a new version based on the new contents.

See |FileContents|_ for more details.

Customizing Argument Keys
-------------------------

Some arguments might need to define their own notion of equality for the purposes of
memoization. These arguments should have a ``__cache_key__()``. It can return anything that can be
made hashable with (|hashable|_). As far as I know, every python object can be made hashable with
|hashable|_. If ``__cache_key__()`` is not found, the object itself is used as the key.

Some arguments represent "versioned resources," in the sense that old versions are not useful
(rarely reused). In this case, ``__cache_key__()`` should return the name of the resource and
``__cache__ver__()`` should return the version. If ``__cache_ver__()`` is not found, a constant is
used. If the version changes, then the older version is replaced rather than appended to.

Using in the Cloud
------------------

- Fine-grain persistence

- Cloud storage path

Using the CLI
-------------

There is a |CLI|_ as well. It can memoize UNIX or other commands from the shell.

Detecting Changes
-----------------

If any global variables (including other functions) referenced by the target change, the cache is
invalidated. I use |inspect.getclosurevars|_ to read these.

.. code:: python

    >>> i = 42
    >>> def bar(x):
    ...     return x+1
    >>> def foo():
    ...     return bar(i)

    >>> import inspect
    >>> inspect.getclosurevars(foo)
    ClosureVars(nonlocals={}, globals={'bar': <function bar at 0x7fe396b32940>, 'i': 42}, builtins={}, unbound=set())

To assess if a function has changed, I compare the closure-variables and the compiled bytecode
(e.g., ``foo.__code__.co_code``). See |determ_hash|_ for more details.

Extra State
-----------

Sometimes, language-level closures are not enough to track state. For this, the user can supply
``memoize(..., extra_function_state=callable_obj)``. If the return value of ``callable_obj``
changes, then the cahce is dropped.

TODO: extra_system_state

`Time-to-live (TTL)`_ can easily be supported this way. For example, the memoized function may be an
API that you can call afresh every minute, but need to cache it between those calls. See
|TTLInterval|_ for more details.

Customizing Behavior
--------------------

Storing the whole argument is usually overkill; just storing a hash will do (the default
behavior). Python's |hash|_ will return different values across different runs, so I use
|determ_hash|_.  If for some reason you *do* want to keep the whole object, set ``memoize(...,
use_hash=False)``.

By default, the index entry just holds an object key and the object store maps that to the actual
returned object. This level of indirection means that the index is small and can be loaded quickly
even if the returned objects are big. If the returned objects are small, you can omit the
indirection by setting ``memoize(..., use_obj_store=False)``.

By default, only the object size (not index metadata) is counted towards the size of retaining an
object, but if the object is stored in the index, the object size will be zero.  then the
metadata. Set ``memoize(..., use_metadata_size)`` to include metadata in the size calculation. This
is a bit slower, so it is not the default.

By default, the cache is only culled to the desired size just before serialization. To cull the
cache after every store, set ``memoize(..., fine_grain_eviction=True)``. This is useful if the cache
would run out of memory without an eviction.

Be aware of ``memoize(..., verbose=True|False)``. If verbose is enabled, the cache will emit a
report at process-exit saying how much time was saved. This is useful to determine if caching is
"worth it."

See the `API reference`_ for more details than you ever wanted to know.

.. _`time-to-live (TTL)`: https://en.wikipedia.org/wiki/Time_to_live
.. _`pure`: https://en.wikipedia.org/wiki/Pure_function
.. _`API reference`: http://example.com
.. |inspect.getclosurevars| replace:: ``inspect.getclosurevars``
.. _`inspect.getclosurevars`: https://docs.python.org/3/library/inspect.html#inspect.getclosurevars
.. |__getstate__/__setstate__| replace:: ``__getstate__/__setstate__``
.. _`__getstate__/__setstate__`: https://docs.python.org/3/library/pickle.html#object.__getstate__
.. |hash| replace:: ``hash``
.. _`hash`: https://docs.python.org/3/library/functions.html?highlight=hash#hash
.. |FileContents| replace:: ``FileContents``
.. _`FileContents`: http://example.com
.. |hashable| replace:: ``hashable``
.. _`hashable`: http://example.com
.. |TTLInterval| replace:: ``TTLInterval``
.. _`TTLInterval`: http://example.com
.. |determ_hash| replace:: ``determ_hash``
.. _`determ_hash`: http://example.com

.. TODO FileContents URL
