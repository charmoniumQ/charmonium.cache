========
Features
========

Prior Work
----------

- The most obvious option is to manually load and store a map from arguments to
  their outputs in the filesystem. **Significant shortcoming:** this requires
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

- Another option is guard the whole invocation with Make. **Significant
  Shortcoming**: This more difficult to adopt: all functions have to be
  refactored to operate on files. It also goes outside of the language, which
  loses some of the power of Python.

Feature Matrix
--------------

+------------------+----------+-----------+--------+-------+------+-----------+---------+--------+------+
|                  |Usefulness|Correctness|Ease    |Bounded|Shared|Replacement|Versioned|Overhead|Python|
|                  |          |           |of      |       |      |Policy     |Resources|aware   |3.x   |
|                  |          |           |adoption|       |      |           |         |        |      |
|                  |          |           |        |       |      |           |         |        |      |
|                  |          |           |        |       |      |           |         |        |      |
+==================+==========+===========+========+=======+======+===========+=========+========+======+
|Manually          |    🔶    |    ❌     |   ❌   |  ❌   |  ✅  |    ❌     |    ❌   |   ❌   |  ✅  |
|load/store to/from|          |           |        |       |      |           |         |        |      |
|FS                |          |           |        |       |      |           |         |        |      |
+------------------+----------+-----------+--------+-------+------+-----------+---------+--------+------+
|Other             |    🔶    |    ❌     |   ✅   |  🔶   |  ❌  |    ❌     |    ❌   |   ❌   |  ✅  |
|libs              |          |           |        |       |      |           |         |        |      |
+------------------+----------+-----------+--------+-------+------+-----------+---------+--------+------+
|ORM               |    ✅    |    ❌     |   ❌   |  ❌   |  ✅  |    ✅     |    ❌   |   ❌   |  ✅  |
+------------------+----------+-----------+--------+-------+------+-----------+---------+--------+------+
|IncPy             |    ✅    |    ✅     |   ✅   |  ❌   |  ❌  |    ❌     |    ❌   |   ❌   |  ❌  |
+------------------+----------+-----------+--------+-------+------+-----------+---------+--------+------+
|Make              |    🔶    |    ✅     |   ❌   |  ❌   |  ✅  |    ❌     |    ✅   |   ❌   |  ✅  |
+------------------+----------+-----------+--------+-------+------+-----------+---------+--------+------+
|charmonium.cache  |    ✅    |    ✅     |   ✅   |  ✅   |  ✅  |    ✅     |    ✅   |   ✅   |  ✅  |
+------------------+----------+-----------+--------+-------+------+-----------+---------+--------+------+

1. **Useful**: When the code and data remain the same, and their entry has not
   yet been evicted, the function should be faster. Usefulness is quantified by
   the duration over which results can be used:

   - ❌: only useful within the same process (perhaps they use in memory
     storage)
   - 🔶: only useful within the same machine
   - ✅: useful between machines

2. **Correct**: When the inputs changes, the function should be recomputed. For
   experimentalists to be confident in the result of experiments, the cache
   **cannot** have a chance of impacting correctness; it must invalidate itself
   automatically.

   - ❌: only correct with respect to function arguments
   - ✅: correct with respect to function arguments, `closure`_, and source code

  This library has the latter degree of correctness. See the tests in
  ``tests/test_code_change.py``.

3. **Easy to adopt**: When using the cache, the calling code should not have to
   change, and the defining code should change minimally.

   - ❌: requires non-trivial work to adopt
   - ✅: change at most one line of the definition and nothing in the call-sites, in the common case. For example,

   .. code:: python

    >>> from charmonium.cache import memoize
    >>> @memoize() # this is the only line I have to add
    ... def function(input1, input2):
    ...     return input1 + input2
    ... 
    >>> # these calls don't change
    >>> function(3, 4)
    7
    >>> function(5, 6)
    11

4. **Bounded**:

   - ❌: Not bounded
   - 🔶: bounded number of entries
   - ✅: bounded size in storage; this is more tangible and usable for
     end-users.

5. **Shared between functions**: The cache capacity should be shared between
   different functions. This gives "important" functions a chance to evict
   "unimportant" ones (no need for static partitions).

6. **Replacement policy**: Data has to be evicted to maintain bounded size.

   - ❌: ad-hoc replacement
   - 🔶: replacement based on recency
   - ✅: replacement based on recency, data-size, and compute-time
     ("function-based replacement policy" in Podlipnig's terminology
     [Podlipnig]_)

   The most common replacement policy is LRU, which does not take into account
   data-size or compute-time. This is permissible when all of the cached items
   are resulting from the same computation (e.g. only caching one
   function). However, since this cache is shared between functions, it may
   cache computations with totally different size/time characteristics.

7. **Supports versioned-resources**: Some variables represent a "versioned
   resource:" with high probability, the version either stays the same or
   changes to a novel value, rarely returning to a previously-seen value. Note
   that this need not be a numeric version; its content can be its version. We
   want to *invalidate* entries based on an older version. The old entries may
   have been evicted by the eviction algorithm anyway, but invalidation
   *guarantees* its eviction.

   For example, data files are a versioned resource; if they change, their value
   old value is likely not revisited. Not only should the cache insert the new
   version as a new entry (that is *correctness*), it should delete the old one
   entry.

8. **Overhead aware**: In cases where the overhead of the cache is greater than
   the time saved, the cache should warn the user to change their code. Although
   this does not eliminate `cache thrashing`_, it will raise problematic
   behavior to the human engineer for further remediation.

9. **Python 3.x**

Other features of ``charmonium.cache``:

- `One- or two-level`_ caching

- Time-to-live (TTL)

- Lossy or non-lossy key compression

- Exported static typing (PEP 561 and PEP 612).

Limitations and Future Work
---------------------------

1. **Requires** `pure functions`_: A cache at the language level requires the
   functions to be pure at a language level. Remarkably, this cache is correct
   for functions that use global variables in their closure. However,
   system-level variables such as the file-system are sources of impurity.

   Perhaps future research will find a way to encapsulate the system
   variables. One promising strategy is to intercept-and-virtualize external
   syscalls (Vagrant, VirtualBox); Another is to run the code in a sandboxed
   environment (Docker, Nix, Bazel). Both of these can be paired with the cache,
   extending its correctness guarantee to include system-level variables.

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
   computational tasks. The cache function could use the incoming subgraph as
   the key for the cache. In steady-state, only the highest nodes will be
   cached, since they experience more reuse. If they hit in the cache, none of
   the inputs need to be accessed/reused. Future development of my cache may
   leverage Dask's task DAG.

4. **Thread-safety**

5. **Remove orphans**

.. _`pure functions`: https://en.wikipedia.org/wiki/Pure_function
.. _`cache thrashing`: https://en.wikipedia.org/wiki/Thrashing_(computer_science)
.. _`LRU`: https://en.wikipedia.org/wiki/Cache_replacement_policies#Least_recently_used_(LRU)
.. _`closure`: https://en.wikipedia.org/wiki/Closure_(computer_programming)
.. _`decorator`: https://en.wikipedia.org/wiki/Python_syntax_and_semantics#Decorators
.. _`functools.lru_cache`: https://docs.python.org/3/library/functools.html#functools.lru_cache
.. _`joblib.Memory`: https://joblib.readthedocs.io/en/latest/memory.html
.. _`Klepto`: https://klepto.readthedocs.io/en/latest/
.. _`Cachier`: https://github.com/shaypal5/cachier
.. _`IncPy`: https://web.archive.org/web/20120703015846/http://www.pgbovine.net/incpy.html
.. _`python-memoization`: https://github.com/lonelyenvoy/python-memoization
.. _`Object-Relational Mappings`: https://en.wikipedia.org/wiki/Object%E2%80%93relational_mapping
.. _`lazily evaluating`: https://en.wikipedia.org/wiki/Lazy_evaluation
.. _`Dask`: https://docs.dask.org/en/latest/
.. _`mypy`: http://mypy-lang.org/
.. _`pyright`: https://github.com/microsoft/pyright
