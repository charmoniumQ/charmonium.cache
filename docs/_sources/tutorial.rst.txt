Tutorial
========

Cache Functionality
-------------------

The cache is organized into an **index** and an
:py:class:`~charmonium.cache.ObjStore`. The index maps **keys** to
**entries**. Each entry (usually) holds an **object key** that maps to an
**object** in the object store. The object is the serialized return value of the
function.

The key is a tuple of **subkeys**. The index is hierarchical on each subkey (a
dict of dict of dicts etc.). Each subkey is either a lookup or match
subkey. During an insert, if a **lookup subkey** is not found in the index, the
subkey is *inserted beside* the non-matching subkeys. If a **match subkey** is
not found, the subkey *replaces* the old subkey.

This replacing behavior saves space when revisiting prior versions is rare. A
function's source-code is monotonic; there is little use in holding results form
a prior source-code version. While a healthy replacement policy may have evicted
the old version on its own, a match subkey *guarantees* it gets evicted.

The key has five subkeys:

1. The state of the system (match): this includes the package version

2. The function name (lookup)

3. The function version (match): this includes the source-code, closure-state,
   and memoization configuration.
   
4. The arguments (lookup): this can be customized by ``__cache_key__()`` but
   defaults to the object itself.

5. The argument versions (match): this can be customized by ``__cache_ver__()``,
   but defaults to a constant.

Different functions share a backend index and function store, and we will see
why in a moment.

How to Use
----------

First you need to identify candidates for memoization.

- They should be *mostly* `pure`_. The library is correct in the presence of
  global variables, if they change frequently, it will degrade performance.

- Likewise, The function and those it depends on should be relatively stable.

- The function should have a high rate of reused arguments.

- The returned value should have a low data storage size. You can customize the
  returned object with |__getstate__|_.

- The function should have a long compute time, so memoization can save a lot of
  work.

Note that multiple functions are cached in the same backend store. This way, a
good candidate for memoization can "steal space" from bad candidates, as long as
the replacement policy is decent.

Once you have your candidate, simply add :py:func:`~charmonium.cache.memoize` to the line above the
function definition. Per-function customizations go inside the parens. For
example,

.. code:: python

    >>> from charmonium.cache import memoize
    >>> @memoize()
    ... def squared(x):
    ...     print(f"squaring {x}")
    ...     return x**2
    ... 
    >>> squared(2)
    squaring 2
    4
    >>> squared(2)
    4

Group-wide customizations are applied after definition through
:py:func:`~charmonium.cache.MemoizedGroup`. For example, size is applied like:

.. code:: python

    >>> from charmonium.cache import MemoizedGroup
    >>> squared.group = MemoizedGroup(size="100KiB")

Customizing Argument Keys
-------------------------

Some arguments might need to define their own notion of equality for the
purposes of memoization. These arguments should have a ``__cache_key__()``. It
can return anything that can be made hashable with
(:py:func:`~charmonium.cache.hashable`). As far as I know, every python object can
be made hashable with hashable. If ``__cache_key__()`` is not found, the object
itself is used as the key. This yields basic memoization.

Some arguments represent "versioned resources," in the sense that old versions
are not useful (rarely reused). In this case, ``__cache_key__()`` should return
the name of the resource and ``__cache__ver__()`` should return the version. If
``__cache_ver__()`` is not found, a constant is used. If the version changes,
then the older version is replaced rather than appended to.

If you can't modify the class, you can monkey-patch the object. See :py:func:`~with_attr`.

.. code:: python

    obj = with_attr(obj, "__cache_key__", lambda: ...)

Capturing Filesystem Side-Effects
---------------------------------

Sadly, not all code is pure; many times, legacy code has impure side effects on
the filesystem. To make legacy code memoizable, the library has a
:py:class:`~charmonium.cache.FileContents` helper. This class represents a
filepath **and its contents**. ``fc.__cache_key__()`` returns the path while
``fc.__cache_ver__()`` returns the contents. Furthemore, ``pickle.dumps(fc)``
dumps a snapshot of the contents, while ``pickle.loads(fc_ser)`` restores those
contents.

Suppose we have the following impure function:

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

This can be cached. If you give a ``src`` with the same path and same contents,
then the output will be recalled instead of computed (``long_function`` need not
be called).

See :py:class:`~charmonium.cache.FileContents` for more details.

Adapting Old Code
-----------------

Suppose you wish to speed up an application which makes usage of this function
called ``work``.

.. code:: python

    def work(input1, input2):
        ...

Memoization is most effective when the function is pure, so ``work`` needs to be
purified. This can be accomplished with minimal code change by creating a
**wrapper function** that maintains the same signature, but sets up a call to a
pure function.

.. code:: python

    # Signature does not change; compatibility maintained
    def work(input1, input2):
        # Defer to FileContents
        real_input1 = FileContents(input1)

        # Make a custom cache key
        input2.__cache_key__ = lambda: ...

        # Turn global variables into parameters
        input3 = global_var

        ret = _real_work(input1, input2, input3)

        # Output side-effects
        output.append(ret)

        return ret

    @memoize()
    def _real_work(input1, input2, global_var):
        # old code, unchanged
        ...

Detecting Changes in Functions
------------------------------

If any global variables (including other functions) referenced by the target
change, the cache is invalidated. I use |inspect.getclosurevars|_ to read these.

.. code:: python

    >>> i = 42
    >>> def bar(x):
    ...     return x+1
    >>> def foo():
    ...     return bar(i)

    >>> import inspect
    >>> inspect.getclosurevars(foo)
    ClosureVars(nonlocals={}, globals={'bar': <function bar at ...>, 'i': 42}, builtins={}, unbound=set())

To assess if a function has changed, I compare the closure-variables and the
compiled bytecode (e.g., ``foo.__code__.co_code``). See
:py:func:`~charmonium.cache.determ_hash` for more details.

Using in the Cloud
------------------

The library can be used to reuse results *between* machines, but you must
satisfy some invariants:

- Use a pickler that will work between the platforms in question. Consider OS,
  Python version, and library versions.

- Use an :py:class:`~charmonium.cache.ObjStore` that is accessible between the
  machines in question. :py:class:`~charmonium.cache.DirObjStore` is accessible
  between machines if you provide a :py:class:`~charmonium.cache.PathLike`
  object that is accessible between machines. For example, `Universal Pathlib`_
  provides a PathLike object representing an AWS S3 path or a GitHub path.

- The object store should support atomic concurrent accesses to the same key. If
  there is a write-write race, it doesn't matter which one wins, as long as the
  write is atomic (not mangling together both writes). If there is a read-write
  race, the reader can see the value before the writer or after, but not during.

- Consider setting fine-grain persistence
  (``@memoized(fine_grain_persistence=True)``) and using a lock
  (``MemoizedGroup(..., lock=RWLock())``). Without fine-grain persistence, if
  the processes overlap, then whichever process "wins" will overwrite the index
  of the others. In the following example, even though ``f(1)`` and ``f(2)``
  were both computed, only one will be remembered, depending on which write
  "wins the race".

  ::

    Machine 1                        | Machine 2:
    ---------------------------------+--------------------------------
    read index; index = {}           | read index; index = {}
    compute f(1); index = {1: f(1)}  | compute f(2); index = {2: f(2)}
    write index; index = {1: f(1)}   | write index; index = {2: f(2)}

  But with fine-grain persistence, the index is read before every function-call
  and read-and-written after every function call. Reads and writes to the index
  are guarded by the readers-writer lock. This permits read
  concurrency. Evaluating misses (actually doing ``f(x)``) can procede without
  locks.


  ::

    Machine 1                        | Machine 2:
    -------------------------------------------------------------------------
    read index; index = {}           | read index; index = {}
    compute f(1); index = {1: f(1)}  | compute f(2); index = {2: f(2)}
    rmw index; index = {1: f(1)}     | blocked
    blocked                          | rmw index; index = {1: f(1), 2: f(2)}


  This is important if you want machines to be able to reuse values that another
  machine produced concurrently.

Using the CLI
-------------

There is a :doc:`cli` as well. It can memoize UNIX or other commands from the shell.

Extra State
-----------

Sometimes, language-level closures are not enough to track state. For this, the
user can supply ``memoize(..., extra_function_state=callable_obj)``. The return
value of ``callable_obj`` is a part of the 3rd match subkey. When it changes,
then the cache for that function is dropped.

State can be added to the whole system by ``MemoizedGroup(...,
extra_system_state=callable_obj)``. The return value of ``callable_obj`` is a
part of the 1st match subkey. When it changes, the whole cache is dropped.

`Time-to-live (TTL)`_ is a common cache policy. For example, the memoized
function may be an API that you can call afresh every minute, but need to cache
it between those calls. TTL can easily be supported this way at either the
function or group-level by customizing ``extra_function_state`` and
``extra_system_state``. See :py:class:`~charmonium.cache.TTLInterval` for more
details.

Other Behaviors
---------------

By default, the index entry just holds an object key and the object store maps
that to the actual returned object. This level of indirection means that the
index is small and can be loaded quickly even if the returned objects are
big. If the returned objects are small, you can omit the indirection by setting
``memoize(..., use_obj_store=False)``.

By default, only the object size (not index metadata) is counted towards the
size of retaining an object, but if the object is stored in the index, the
object size will be zero.  then the metadata. Set ``memoize(...,
use_metadata_size)`` to include metadata in the size calculation. This is a bit
slower, so it is not the default.

By default, the cache is only culled to the desired size just before
serialization. To cull the cache after every store, set ``memoize(...,
fine_grain_eviction=True)``. This is useful if the cache would run out of memory
without an eviction.

By default, the cache only stores a hash of the keys, which is faster and
smaller. Set ``memoize(..., lossy_compression=False)`` to store the whole keys
(useful for debugging).

Unfortunately, Python's |hash|_ will return different values across different
runs, so I use :py:func:`~charmonium.cache.determ_hash`.  If for some reason you
*do* want to keep the whole object, set ``memoize(..., use_hash=False)``.

Be aware of ``memoize(..., verbose=True|False)``. If verbose is enabled, the
cache will emit a report at process-exit saying how much time was saved. This is
useful to determine if caching is "worth it."

By default, I use the Greedy-Dual-Size Algorithm from [Cao et al.]_. This can be
customized by specifying ``memoize(replacement_policy=YourPolicy())`` where
``YourPolicy`` inherits from :py:class:`~charmonium.cache.ReplacementPolicy`.`

See :py:class:`~charmonium.cache.Memoized` and :py:class:`~charmonium.cache.MemoizedGroup` for details.

.. _`time-to-live (TTL)`: https://en.wikipedia.org/wiki/Time_to_live
.. _`pure`: https://en.wikipedia.org/wiki/Pure_function
.. _`Universal Pathlib`: https://github.com/Quansight/universal_pathlib
.. |inspect.getclosurevars| replace:: ``inspect.getclosurevars``
.. _`inspect.getclosurevars`: https://docs.python.org/3/library/inspect.html#inspect.getclosurevars
.. |__getstate__| replace:: ``__getstate__``
.. _`__getstate__`: https://docs.python.org/3/library/pickle.html#object.__getstate__
.. |hash| replace:: ``hash``
.. _`hash`: https://docs.python.org/3/library/functions.html?highlight=hash#hash
