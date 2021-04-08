================
charmonium.cache
================

Provides a decorator for caching a function. Whenever the function is called
with the same arguments, the result is loaded from the cache instead of
computed. If the arguments, source code, or enclosing environment have changed,
the cache recomputes the data transparently (no need for manual invalidation).

The use case is meant for iterative development, especially on scientific
experiments. Many times a developer will tweak some of the code but not
all. Often, reusing prior intermediate computations saves a significant amount
of time every run [Guo]_.

While there are other libraries for memoization, I believe this one is unique because it is:

- correct with respect to source-code changes
- useful across machines
- easy to adopt

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

Goals
-----

All prior work I have found fails one or more of these goals in a significant
way:

1. **Useful**: When the code and data remain the same, and their entry has not
   yet been evicted, the function should be faster. Usefulness is quantified by
   the duration over which results can be used:

   - ❌: only *useful* within the same process (perhaps they use in memory storage)
   - 🔶: only *useful* within the same machine
   - ✅: *useful* between machines

2. **Correct**: When the inputs changes, the function should be recomputed. For
   experimentalists to be confident in the result of experiments, the cache
   **cannot** have a chance of impacting correctness; it must invalidate itself
   automatically.

   - ❌: only *correct* with respect to function arguments
   - ✅: *correct* with respect to function arguments, `closure`_, and source code

3. **Easy to adopt**: When using the cache, the calling code should not have to
   change, and the defining code should change minimally.

   - ❌: requires non-trivial work to adopt
   - ✅: change at most one line of the definition and nothing in the call-sites.

4. **Bounded**:

   - ❌: Not bounded
   - 🔶: *bounded* number of entries
   - ✅: *bounded* size in storage; this is more tangible and usable for end-users.

5. **Replacement policy**: Data has to be evicted to maintain bounded size.

   - ❌: ad-hoc replacement
   - 🔶: replacement based on recency (e.g. `LRU`_)
   - ✅: replacement based on recency, data-size, and compute-time
     ("function-based replacement policy" in Podlipnig's terminology
     [Podlipnig]_)

6. **Supports invalidation**: Invalidation allows the cache to more
   intelligently choose values for eviction. Some variables represent a
   "versioned resource:" with high probability, the version either stays the
   same or changes to a novel value, rarely returning to a previously-seen
   value. Note that this need not be a numeric version; its content can be its
   version. We want to *invalidate* entries based on an older version. The old
   entries may have been evicted by the eviction algorithm anyway, but
   invalidation *guarantees* its eviction.

   For example, data files are a versioned resource; if they change, their value
   old value is likely not revisited. Not only should the cache insert the new
   version as a new entry (that is *correctness*), it should delete the old one
   entry.

7. **Shared between functions**: The cache capacity should be shared between
   different functions. This gives "important" functions a chance to evict
   "unimportant" ones.

8. **Overhead aware**: In cases where the overhead of the cache is greater than
   the time saved, the cache should warn the user to change their code. Although
   this does not eliminate `cache thrashing`_, it will raise problematic
   behavior to the human engineer for further remediation.

9. **Python 3.x**

Prior work
----------

- The most obvious option is to manually load and store a map from arguments to
  their outputs in the filesystem. **Significant shorcoming:** this requires
  significant engineering effort to adopt and maintain.

- There are many existing memoization libraries (`functools.lru_cache`_,
  `joblib.Memory`_, `Klepto`_, `Cachier`_, `python-memoization`_). However,
  these all suffer similar shortcomings. Some do slightly better,
  ``joblib.Memory`` has a bound in size; some are worse ``functools.lru_cache``
  is only useful within the process. **Significant shortcoming:** none of them
  are correct when the source code changes.

- `Object-Relational Mappings`_ (ORMs) can save objects into a relational
  database. However, one would have to change the calling code to lookup the
  objects if they exist and recompute them otherwise. **Significant
  shotcoming:** This still requires significant effort to adopt and is not
  correct when the source code changes.

- [Guo]_ attempted to fix the same problem with `IncPy`_. IncPy is a
  modification to CPython itself, so it can do better than a language-level
  library. For example, IncPy can maintain correctness with respect to some
  external state and it automatically knows when a function is pure and worth
  caching. **Significant shortcoming:** IncPy only supports Python 2.6.

.. `DiskCache`_ is a backend, while my cache is a frontend. In the future, my
   cache may rely on DiskCache.

+------------------+----------+-----------+-----------+-------+-----------+------------+------+--------+--------+
|                  |Usefulness|Correctness|Transparent|Bounded|Replacement|  Supports  |Shared|Overhead| Python |
|                  |          |           |           |       |  policy   |invalidation|      | aware  |  3.x   |
|                  |          |           |           |       |           |            |      |        |        |
|                  |          |           |           |       |           |            |      |        |        |
|                  |          |           |           |       |           |            |      |        |        |
+==================+==========+===========+===========+=======+===========+============+======+========+========+
|Manually          |  🔶[#]   |    ❌     |    ❌     |  ❌   |    ❌     |     ✅     |  ✅  |   ❌   |   ✅   |
|load/store to/from|          |           |           |       |           |            |      |        |        |
|FS                |          |           |           |       |           |            |      |        |        |
+------------------+----------+-----------+-----------+-------+-----------+------------+------+--------+--------+
|Other             |    🔶    |    ❌     |    ✅     |  🔶   |    ❌     |     ❌     |  ❌  |   ❌   |   ✅   |
|memoization       |          |           |           |       |           |            |      |        |        |
|libs              |          |           |           |       |           |            |      |        |        |
+------------------+----------+-----------+-----------+-------+-----------+------------+------+--------+--------+
|ORM               |    ✅    |    ❌     |    ❌     |  ❌   |    ✅     |     ✅     |  ✅  |   ❌   |   ✅   |
+------------------+----------+-----------+-----------+-------+-----------+------------+------+--------+--------+
|IncPy             |    ✅    |    ✅     |    ✅     |  ❌   |    ❌     |     ✅     |  ✅  |   ❌   |   ❌   |
+------------------+----------+-----------+-----------+-------+-----------+------------+------+--------+--------+
|charmonium.cache  |    ✅    |    ✅     |    ✅     |  ✅   |    ✅     |     ✅     |  ✅  |   ✅   |   ✅   |
+------------------+----------+-----------+-----------+-------+-----------+------------+------+--------+--------+

Implementation
--------------

First, the cache holds a map from keys (derived from function arguments) to the
returned values. But we mentioned that there are also "versioned resources." For
example, a file argument that might change, but rarely revisits an older
version. The cache should look up the entry based on every non-versioned
argument and then check to see if the versioned arguments match. If they do, the
entry is valid, otherwise the entry needs to be replaced, not just ignored.

::

     # cache is a mapping from Key to Pair[Key, Value]
     key_to_lookup = ...
     key_to_check = ...
     if key_to_lookup in cache:
         entry = cache[key_to_lookup]
         if entry.key_to_check = key_to_check
             # hit
             return entry
         else:
             # hit in cache, but entry is stale
             entry = recompute_function()
             cache[key_to_lookup] = entry # overwrite old entry
             return entry
     else:
         # miss
         entry = recompute_function()
         cache[key_to_lookup] = entry
         return entry

In general, the cache might be structured as alternating layers of
keys-to-lookup and keys-to-check.

::

    entry1 = cache[lookup_key1]
    if entry1.key == check_key1:
        entry2 = cache[lookup_key2]
        if entry2.values == check_key2:
           ...

1. The state of the system environment is a key-to-check.
2. The name of the function being called is a key-to-lookup.
3. The source-code, environment, and serialization of that function is a key-to-check.
4. The arguments form a key-to-lookup.
5. The version of each versioned resource argument form a key-to-check..

Plans
-----

Design decisions:
- Use directory trees for fast dropping? No, not all FS support efficiently; Probably faster on avg to use an index file.

Options:
- Store keys in-line, out-of-line
- Store values in-line or out-of-line
- Pickler
- cache_key/cache_ver methods on object
  - Write wrapper if need be
  - Lossy/non-lossy (checksums)
    - Faster persistent-hash or custom persistent-hash
- [X] Lockfile method
- [X] fine_grained_persistence
- [X] fine_grained_eviction
- System-version and function-version

Pre-made setups:
- Lossy checksum for cache_key
- FileContents
- TTL
- LRU, LUV, fn+TTL
- Unhashable types
- Two-level store

Additional features:
- can store unhashable types
- supports TTL
- thread-safe
- process-safe
- optional fine-grained persistence
- read-concurrency among processes
- bounded in size
- replacement policy
- supports invalidation
- shared

Todo
- Delete from two-level store
- Size
- Use index versions to elide load
- Test with impure function
- Measure overhead and savings

The library supports backends in filesystem, cloud storage (AWS S3, Google
Cloud Storage, etc.), or any storage medium supported by `Universal Pathlib`_.

2. **Correct**:

 - In order to maintain correctness for individual calls, I use a checksum of the
   serialization of the arguments and keyword arguments.

 - In order to maintain correctness when the code changes, I serialize the
   function using `dill`_.  Dill serializes the closed-over variables using
   reflection (see ``tests/test_picklers.py``). If this checksum of the
   serialized function changes, all entries for this function are invalidated.

3. **Transparent**: I implement this using a `decorator`_ (one line of
   code added to the function-definition) that wraps the function with
   the same arguments.

   .. code:: python

    >>> @ch_cache.decor() # this is the only line I have to add
    ... def function(input1, input2):
    ...     return input1 + input2

    >>> # these calls don't change
    >>> function(3, 4)
    7
    >>> function(5, 6)
	11

7. **Support version-based invalidation**:

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

Code quality
------------

- The code base is strictly and statically typed with `mypy`_. I export type
  annotations in accordance with `PEP 561`_; clients will benefit from the type
  annotations in this library.

- I have unittests with decent (TODO: X%) coverage.

- I use pylint with few disabled warnings.

- All of the above methods are incorporated into per-commit continuous-testing
  and required for merging with the ``main`` branch; This way they won't be
  easily forgotten.

- I've implemented the complete feature-set in relatively few lines of code. LoC
  count is an imperfect but reasonable metric of how hard something is to
  maintain and how likely it is to contain bugs [Zhang]_.

Limitations and Future Work
---------------------------

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

2. **Suffers cache thrashing**: `Cache thrashing`_ is a performance failure
   where the working-set is so large the entries in entries *never* see reuse
   before eviction. For example:

   .. code:: python

    for i in range(100):
        for j in range(25): # Suppose the returned value is 1 Gb and the cache capacity is 10Gb
            print(cached_function(j))

   The cache can only hold 10 entries at a time, but the reuse is 25 iterations
   away, the older values are more likely to be evicted (in most cache
   replacement policies), so nothing in the cache is able to be reused.

   The best solution is to reimplement the caller to exploit more reuse or not
   cache this function. It seems that the cache would need to predict the
   access-pattern in order to counteract thrashing, which I consider too hard to
   solve in this package. However, I can at least detect cache-thrashing and
   emit a warning. If the overheads are greater than the estimated time saved,
   then thrashing may be present.

3. **Implements only eager caching**: Suppose I compute ``f(g(x))`` where ``f``
   and ``g`` both have substantial compute times and storage. Sometimes nothing
   changes, so ``f`` should be cached to make the program fast. But ``g(x)``
   still has to be computed-and-stored or loaded for no reason. 'Lazy caching'
   would permit ``f`` to be cached in terms of the symbolic computation tree
   that generates its input (``(apply, g, x)``) rather than the value of its input
   (``g(x)``). This requires "`lazily evaluating`_" the input arguments, which
   is difficult in Python and outside the scope of this project.

   However, `Dask`_ implements exactly that: it creates a DAG of coarse
   computational tasks. The cache function could use the incoming subgraph as the
   key for the cache. In steady-state, only the highest nodes will be cached, since
   they experience more reuse. If they hit in the cache, none of the inputs need to
   be accessed/reused. Future development of my cache may leverage Dask's task DAG.

4. **Command-line Tool:** TODO

- --cache: Path
- --env: str
- --key: str
- --version: str
- --version-files: List[Path]
- --comparison: Enum["mtime", "sha1", "crc32", "adler32"]
- --replacement: Enum["LRU", "LUV"]
- --max-size: int
- --verbose: bool
- --write-output/--check-output: bool
- command: List[str]
- Use strace to get input and output paths

For the CLI:

1. The state of the environment and options form a key-to-check.
2. The command[0] is a key-to-lookup.
3. The content of command[0] is a key-to-check
4. command[1:] and --keys form a key-to-lookup.
5. The input files, --version, --version-files, and possibly output files form a key-to-check.

If a lookup is found, the ouput files are either written to the disk or noop

::

    cache_obj = Cache(cache, replacement, max_size)
    inputs = [command[0], comparison(command[0]), command[1:], args, version, *(comparison(file) for file in version_files)]
    stdout, stderr, inputs, expected_outputs = recursively_at(cache_obj, inputs)
    if match and all(comparison(input) == val for input, val in inputs.items()) and all(comparison(output) == val for output, val in expected_outputs.items()):
        if verbose: log hit
        sys.stderr  write bytes stderr
        sys.stdout  write bytes stdout
    else:
        if verbose: log miss
        proc = subprocess.run(command, capture_output=True) with strace
        input_files = [compare(file) for file in proc.input_files]
        output_files = [compare(file) for file in proc.output_files]
        recursively_at(cache_obj, inputs) = Entry(proc.stdout, proc.stderr, input_files, output_files)
        sys.stderr  write bytes stderr
        sys.stdout  write bytes stdout

Works Cited
-----------

.. [Guo] Guo, Philip Jia. *Software tools to facilitate research programming*. Stanford University, 2012. See Chapter 5. https://purl.stanford.edu/mb510fs4943
.. [Podlipnig] Podlipnig, Stefan, and Laszlo Böszörmenyi. "A survey of web cache replacement strategies." *ACM Computing Surveys (CSUR) 35.4* (2003): 374-398. http://www.cs.ucf.edu/~dcm/Teaching/COT4810-Fall%202012/Literature/WebCacheReplacementStrategies.pdf
.. [Zhang] Zhang, Hongyu. "An investigation of the relationships between lines of code and defects." *2009 IEEE International Conference on Software Maintenance*. IEEE, 2009. https://www.researchgate.net/profile/Hongyu-Zhang-46/publication/316922118_An_Investigation_of_the_Relationships_between_Lines_of_Code_and_Defects/links/591e31e1a6fdcc233fceb563/An-Investigation-of-the-Relationships-between-Lines-of-Code-and-Defects.pdf
.. _`PEP 561`: https://www.python.org/dev/peps/pep-0561/
.. _`pure functions`: https://en.wikipedia.org/wiki/Pure_function
.. _`cache thrashing`: https://en.wikipedia.org/wiki/Thrashing_(computer_science)
.. _`LRU`: https://en.wikipedia.org/wiki/Cache_replacement_policies#Least_recently_used_(LRU)
.. _`closure`: https://en.wikipedia.org/wiki/Closure_(computer_programming)
.. _`Universal Pathlib`: https://github.com/Quansight/universal_pathlib/
.. _`dill`: https://dill.readthedocs.io/en/latest/
.. _`decorator`: https://en.wikipedia.org/wiki/Python_syntax_and_semantics#Decorators
.. _`functools.lru_cache`: https://docs.python.org/3/library/functools.html#functools.lru_cache
.. _`joblib.Memory`: https://joblib.readthedocs.io/en/latest/memory.html
.. _`Klepto`: https://klepto.readthedocs.io/en/latest/
.. _`Cachier`: https://github.com/shaypal5/cachier
.. _`DiskCache`: http://www.grantjenks.com/docs/diskcache/
.. _`IncPy`: https://web.archive.org/web/20120703015846/http://www.pgbovine.net/incpy.html
.. _`python-memoization`: https://github.com/lonelyenvoy/python-memoization
.. _`Object-Relational Mappings`: https://en.wikipedia.org/wiki/Object%E2%80%93relational_mapping
.. _`lazily evaluating`: https://en.wikipedia.org/wiki/Lazy_evaluation
.. _`Dask`: https://docs.dask.org/en/latest/
.. _`mypy`: http://mypy-lang.org/
