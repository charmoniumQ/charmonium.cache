======
Theory
======


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
|                  |Usefulness|Correctness|Transparent|Bounded|Replacement|Supports    |Shared|Overhead|Python  |
|                  |          |           |           |       |policy     |invalidation|      |aware   |3.x     |
|                  |          |           |           |       |           |            |      |        |        |
|                  |          |           |           |       |           |            |      |        |        |
|                  |          |           |           |       |           |            |      |        |        |
+==================+==========+===========+===========+=======+===========+============+======+========+========+
|Manually          |  🔶[#]_  |    ❌     |    ❌     |  ❌   |    ❌     |     ✅     |  ✅  |   ❌   |   ✅   |
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

- TODO: Separate ``functools.lru_cache``. Add ``Make``.

- TODO: Additional features:

  - Two-level
  - can store unhashable types
  - supports lossy and non-lossy keys
  - supports TTL
  - thread-safe
  - process-safe
  - optional fine-grained persistence
  - read-concurrency among processes
  - bounded in size
  - replacement policy
  - supports invalidation
  - shared

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

Limitations and Future Work
---------------------------

1. **Requires `pure functions`_**: A cache at the language level requires the
   functions to be pure at a language level. Remarkably, this cache is correct
   for functions that use global variables in their closure. However,
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


Works Cited
-----------

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
.. _`pip install guide`: https://pip.pypa.io/en/latest/installing/
.. _`pyright`: https://github.com/microsoft/pyright
