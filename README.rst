================
charmonium.cache
================

Provides a decorator for caching a function. Whenever the function is called
with the same arguments, the result is loaded from the cache instead of
computed.

Quickstart
----------

::

    $ pip install charmonium.cache

.. code:: python

    >>> import charmonium.cache as ch_cache
    >>> @ch_cache.decor()
    ... def square(x):
    ...     print("computing")
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

There is also a CLI which cache a command based on its file arguments.

::

    $ ch_cache --verbose clang++ source.cpp
    miss for source.cpp@1234deadbeef

    $ ch_cache --verbose clang++ source.cpp
    hit for source.cpp@1234deadbeef

    $ # if the file changes, the command is recomputed
    $ echo >> source.txt
    $ ch_cache --verbose clang++ source.cpp
    miss for source.cpp@baadf00d1234

    $ # if any of the flags change, the command is recomputed
    $ ch_cache --verbose clang++ -g source.cpp
    miss for -g source.cpp@baadf00d1234

    $ # But the old arg-combo still hits
    $ echo >> source.txt
    $ ch_cache --verbose clang++ source.cpp
    hit for source.cpp@baadf00d1234

Use case
--------

The use case is meant for iterative development, especially on scientific
experiments. I often find myself tweaking some of the code but not all. Often,
reusing prior intermediate computations saves minutes of my time every run, in
the manner that `Guo`_ studied.

.. _`Guo`: https://purl.stanford.edu/mb510fs4943

Some developers manually cache their results to disk, but this is onerous to
maintain as their experiment evolves, and the user has to manually delete it
when the code changes. For experimentalists to be confident in the result of
experiments, the cache **cannot** have a chance of impacting correctness; it
must invalidate itself automatically.

Objectives
----------

1. **Useful**: When the code and data remain the same, and their entry has not
   yet been evicted, the function should be faster. “Code and data” includes
   variables that are `closed-over`_.

.. _`closed-over`: https://en.wikipedia.org/wiki/Closure_(computer_programming)

2. **Correct**: When the code or data changes, the function should be
   recomputed. I will assume the function is pure with respect to its parameters
   and closure variables.

3. **Transparent**: When using the cache, the calling code should not have to
   change, and the defining code should change minimally. I have chosen to
   implement accessing the cache as a decorator (one line of code added to the
   function-definition) that wraps the function with the same arguments.

   .. code:: python

    @ch_cache.decor() # this is the only line I have to add
    function(input1, input2):
        return input1 + input2

    # these calls don't change
    function(3, 4)
    function(5, 6)


4. **Bounded in size**: The size of the cache on disk should be bounded.

5. **Replacement policy informed by data-size and compute-time**: Data has to be
   evicted to maintain bounded size, so evictions should be chosen based on
   recency, compute-time, and data-size. However, most algorithms such as `LRU`_
   are only informed on recency.

.. _`LRU`: https://en.wikipedia.org/wiki/Cache_replacement_policies#Least_recently_used_(LRU)

6. **Shared between functions**: The cache capacity should be shared between
   different functions. This gives "important" functions a chance to evict
   "unimportant" ones. This combined with eviction-effectiveness yield a better
   time-saved per storage-used.

7. **Supports invalidation**: Invalidation allows the cache to more
   intelligently choose values for eviction. Some variables represent a
   "versioend resource." With high probability, the version either stays the
   same or increases, rarely returning to a previous value. Note that this need
   not be a numeric version; its content can be its version. We want to
   *invalidate* entries based on an older version. The old entries may have been
   evicted by the eviction algorithm, but invalidation *guarantees* its
   eviction.

   For example, data files are a versioned resource; if they change, their value
   old value is likely not revisited. Not only should the cache insert the new
   version as a new entry (that is *correctness*), it should delete the old one entry.

8. **Low overhead**: The miss-overhead and hit-overhead should both be
   small compared to the computation.

Implementation
--------------

The *index* is a map from from the checksum of the serialization of the
arguments to the function value and metadata. I use a checksum because I don't
need to read the whole arguments; I just need to test them for equality. A hash
pis faster, but it is not stable between runs. The work one has to do to make it
stable is almost as much work as one has to do to generate the serialization
(e.g. a stable-hash would use contents instead of ``id()``, and so would a
serializer).

The *backend* is responsible for storing the index. The backend may choose to
store function values inside the index, or it may choose to insert a layer of
indirection (store a key that maps to the value).

TODO: backend -> object store
TODO: two-level vs one-level

The library supports backends in filesystem, cloud storage (AWS S3, Google
Cloud Storage, etc.), or any storage medium supported by `Universal Pathlib`_.

.. _`Universal Pathlib`: https://github.com/Quansight/universal_pathlib/

This helps me meet the preceding goals:

1. **Useful**: Caching is persistent across runs.

2. **Correct**:

 - In order to maintain correctness for individual calls, I use a checksum of the
   serialization of the arguments and keyword arguments.

 - In order to maintain correctness when the code changes, I serialize the
   function using `dill`_.  Dill serializes the closed-over variables using
   reflection (see ``tests/test_picklers.py``). If this checksum of the
   serialized function changes, all entries for this function are invalidated.

.. _`dill`: https://dill.readthedocs.io/en/latest/

3. **Transparent**: I implement this using a `decorator`_.

.. _`decorator`: https://realpython.com/primer-on-python-decorators/

4. **Bounded in size**: If the size hits the maximum limit, the cache
   transparently selects entries for eviction. This selection is efficiently
   computed in O(n log n) with a heap.

5. **Replacement Policy**:

 - A literature survey by `Podlipnig et al.`_ shows that cache replacement
   strategies should use size and compute-time. `LRU`_ ignores this
   information. While it is plausible a function's cach entries may have the
   same size and compute-time, it is unlikely that all cached functions in the
   system have identical parameters. Using the same cache for different
   functions is beneficial as shown in the next point.

 - The implementation allows an arbitrary "function-based" (in Podlipnig's
   terminology) replacement policy, because it stores the data-size,
   compute-time, and arbitrary data.

.. _`LRU`: https://en.wikipedia.org/wiki/Cache_replacement_policies#Least_recently_used_(LRU)
.. _`Podlipnig et al.`: http://www.cs.ucf.edu/~dcm/Teaching/COT4810-Fall%202012/Literature/WebCacheReplacementStrategies.pdf

6. **Shared between functions**: 

7. **Support invalidation**: The source code of the function and its closed-over
   functions is always considered a versioned resource. When it changes, the cache
   drops all of the entries, rather than saving them (old code probably wouldn't
   be revisited).

   Some function arguments can also be a versioned resource. For example, a
   function that takes the current time of day as an argument. The time never
   reverts (or rarely does for timezone changes or clock corrections).

   Arguments can be considered monotonic with time if they have
   ``__cache_key__(self) -> Any`` and ``__cache_ver__(self) -> Any``. The cache
   adheres to the following pseudo-code:

    ::

     args_cache_keys = [arg.__cache_key__() for arg in args]
     args_cache_vers = [arg.__cache_ver__() for arg in args]
     if arg_cache_keys in cache:
         entry = cache[arg_cache_keys]
         if entry.versions = arg_cache_vers
             # hit
             return entry
         else:
             # hit in cache, but entry is stale
             recompute_function
             cache[arg_cache_keys] = entry # overwrite old entry
             return entry
     else:
         # miss
         recompute_function
         cache[arg_cache_keys] = entry
         return entry


   For example, ``PathContents`` has many of the same methods as ``Path``.
   Additionally, it has ``__cache_key__(self)`` which returns the path (location on
   disk) and ``__cache_ver__(self)`` which returns, a hash of the contents (modtime
   can be used instead of hash) of the file at that path. If a file with the same
   path has new contents, the function is recomputed and the old entry is
   replaced:

   .. code:: python

    >>> @ch_cache.decor()
    ... def length(src: PathContents) -> int:
    ...     print("recalculating length of {src!s}")
    ...     return len(src.read_text())
    >>> with open("/tmp/foo", "w") as f:
    ...     f.write("hello world")
    >>> length(PathContents("/tmp/foo"))
    recalculating
    11
    >>> length(PathContents("/tmp/foo"))
    11
    >>> with open("/tmp/foo", "w") as f:
    ...     f.write("hello world2")
    >>> length(PathContents("/tmp/foo"))
    recalculating
    12
    >>> len(length.obj_store)
    ... 1
    >>> # Only 1 object in the store, so the entry for the old version of /tmp/foo has been dropped.

   ``__cache_key__(self)`` defaults to ``self``, and ``__cache_ver__(self)``
   defaults to ``None``. If you don't define something as a monotonic variable, it
   doesn't act like one; changes will always cause misses never stale-hits.

   In general, the cache might be structured as alternating layers of
   keys-to-lookup and values-to-check.

   ::

    entry1 = cache[key1]
    if entry1.values == values1:
        entry2 = cache[key2]
        if entry2.values == values2:
           ...

   In this cache, I have restricted this for the sake of simplicity to three
   layers: the function's code forms the outer-most value-to-check, then the
   arguments for a key-to-lookup, then the monotonic vairables form a
   value-to-check.

8. **Low overhead**: Overhead primarily comes from these sources: serializing
   the inputs and de/serializing the index (map from the checksum of inputs to
   results). This cache measures its own overhead and emits a warning if the
   cache isn't "pulling its weight."

Code quality
------------

In order to maintain code quality, I use mypy with strict types, unittests with
decent (TODO: X%) coverage, and pylint with few disabled warnings. I export type
annotations in accordance with `PEP 561`_, so clients will benefit from the type
annotations in this library.

.. _`PEP 561`: https://www.python.org/dev/peps/pep-0561/

LoC count is an imperfect but reasonable metric of how hard something is to
maintain and understand (TODO: citation needed). This package implements all fo
the features in relatively (TODO: how many?) few lines of code.

Prior work
----------

- `functools.lru_cache`_ is only useful *within* one run. My cache is useful
  *between* runs, since it uses the disk for persistence. Iterative development
  with an IDE **requires** multiple runs. Their cache is LRU which has no
  eviction-effective guarantee and does not support invalidation.

- `joblib.Memory`_ is not *correct* when the code changes. This is crucial in
  iterative development, because developers do not want to have to manually
  invalidate caches, when some but not all of the code has changed, or risk
  incorrect results if they forget. Their cache is LRU, which is not
  eviction-effective, is bounded by number of elements (not disk size), and does
  not support invalidation.

- `Klepto`_ is not correct when the code changes, bounded by elements not size,
  not eviction-effective (uses LRU), and does not support invalidation.

- `Cachier`_ is not correct when the code changes, bounded by elements not size,
  not eviction-effective (uses a handmade algorithm), and does not support
  invalidation.

- `IncPy`_ is more useful since it can memoize functions automatically without a
  decorator. It is more correct since it can detect when the function is
  impure. It has no replacement policy or size bound, but it supports
  invalidation instead.

  However, implementing IncPy requires modifying the Python interpreter and such
  modification has only been made for Python 2.6.

- `DiskCache`_ is a backend, while my cache is a frontend. In the future, my
  cache may rely on DiskCache.

.. _`functools.lru_cache`: https://docs.python.org/3/library/functools.html#functools.lru_cache
.. _`joblib.Memory`: https://joblib.readthedocs.io/en/latest/memory.html
.. _`Klepto`: https://klepto.readthedocs.io/en/latest/
.. _`Cachier`: https://github.com/shaypal5/cachier
.. _`DiskCache`: http://www.grantjenks.com/docs/diskcache/
.. _`IncPy`: https://purl.stanford.edu/mb510fs4943

Limitations
----------

1. **Requires `pure functions`_**: A cache at the language level requires the
   functions to be pure at a language level. Remarkably, this cache is correct
   for functions that use global variables in their closure (impure with
   arguments, but pure with the pair of arguments and closure). However,
   system-level variables such as the file-system are sources of impurity.

   Perhaps future research will find a way to encapsulate the system variables. One
   promising strategy is to intercept-and-virtualize external syscalls (Vagrant,
   VirtualBox); Another is to run the code in a sandboxed environment (Docker, Nix,
   Bazel). Both of these can be paired with the cache, extending its correctness
   guarantee to include system-level variables.

.. _`pure functions`: https://en.wikipedia.org/wiki/Pure_function

2. **Suffers cache thrashing**: `Cache thrashing`_ is a performance failure
   where the working-set is so large the entries in entries *never* see reuse
   before eviction. For example:

   .. code:: python

    for i in range(100):
        for j in range(25): # Suppose the returned value is 1 Gb and the cache capacity is 10Gb
            print(cached_function(j))

   The cache can only hold 10 entries at a time, but the reuse is 25 iterations
   away, so nothing in the cache is able to be reused.

   The best solution is to reimplement the caller to exploit more reuse or not
   cache this function. At first glance, the cache would need to predict the
   access-pattern in order to counteract thrashing, which I consider too hard to
   solve in this package. However, I can at least detect cache-thrashing and emit a
   warning. If the overheads are greater than the estimated time saved, then
   thrashing may be present.

.. _`cache thrashing`: https://en.wikipedia.org/wiki/Thrashing_(computer_science)#Other_uses

3. **Implements only eager caching**: Suppose I compute ``f(g(x))`` where ``f``
   and ``g`` both have substantial compute times and storage. Sometimes nothing
   changes, so ``f`` should be cached to make the program fast. But ``g(x)``
   still has to be computed-and-stored or loaded for no reason. 'Lazy caching'
   would permit ``f`` to be cached in terms of the symbolic computation tree
   that generates its input (``g-of-x``) rather than the value of its input
   (``g(x)``). This requires "`lazily evaluating`_" the input arguments, which
   is difficult in Python and outside the scope of this project.

   However, `Dask`_ implements exactly that: it creates a DAG of coarse
   computational tasks. The cache function could use the incoming subgraph as the
   key for the cache. In steady-state, only the highest nodes will be cached, since
   they experience more reuse. If they hit in the cache, none of the inputs need to
   be accessed/reused. Future development of my cache may leverage Dask's task DAG.

.. _`lazily evaluating`: https://en.wikipedia.org/wiki/Lazy_evaluation
.. _`Dask`: https://docs.dask.org/en/latest/

4. **Cache is not shared between machines**: TODO
