Tutorial
========

How to Use
----------

First you need to identify candidates for memoization.

- They should be *mostly* `pure`_. The library is correct in the presence of
  global variables, if they change frequently, it will degrade performance.

- File IO operations should be done through ``FileContents`` (see
  below). Alternatively, do the File IO in a wrapper function around a pure
  inner function.

- Likewise, The function and those it depends on should be relatively stable.

- The function should have a high rate of reused arguments.

- The returned value should have a low data storage size. You can customize the
  returned object with |__getstate__|_.

- The function should have a long compute time, so memoization can save a lot of
  work.

Note that multiple functions are cached in the same backend store. This way, a
good candidate for memoization can "steal space" from bad candidates, as long as
the replacement policy is decent.

Once you have your candidate, simply add :py:func:`~charmonium.cache.memoize` to
the line above the function definition. Per-function customizations go inside
the parens. For example,

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

Capturing Filesystem Side-Effects
---------------------------------

Sadly, not all code is pure; many times, legacy code has impure side effects on
the filesystem. To make legacy code memoizable, the library has a
:py:class:`~charmonium.cache.FileContents` helper. This class represents a
filepath **and its contents**.

Suppose we have the following impure function:

.. code:: python

    def copy(src: str) -> None:
        with open(src, "rb") as src_f:
            result = long_function(src_f.read())
        with open(src + "_copy", "wb") as dst_f:
            dst_f.write(result)

    copy("test")

We can convert this to a pure function by:

.. code:: python

    @memoize()
    def pure_copy(src: FileContents) -> FileContents:
        # FileContents acts like a string file-name
        dst = src + "_copy"
        copy(src, dst)
        return dst

    copy(FileContents("test"))

- :py:class:`~charmonium.cache.FileContents` has a custom hash function that
  includes a hash of its contents; if the ``src`` file changes, the hash
  changes, and `pure_copy` is rerun.

- :py:class:`~charmonium.cache.FileContents` has a custom de/serialization
  includes the contents; when the memoization of ``pure_copy`` misses, it will
  run the underlying ``copy`` and store the new contents of ``dst``. When
  memoization of ``pure_copy`` hits, it will deserialize those contents and
  write them into ``dst``, emulating the side-effect of ``copy``.


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

    # Old signature, new body
    def work(input1, input2):

        # Defer to FileContents
        real_input1 = FileContents(input1)

        # Make a custom cache key (see `How It Works`)
        input2.__cache_key__ = lambda: ...

        # Turn global variables into parameters
        input3 = global_var

        ret = _real_work(real_input1, input2, input3)

        # Output side-effects
        output.append(ret)

        return ret

    # New signature, old body
    @memoize()
    def _real_work(input1, input2, global_var):
        ...

Using in the Cloud
------------------

The library can be used to reuse results *between* machines, but you must
satisfy some invariants:

- Use a pickler that will work between the platforms in question. Consider OS,
  Python version, and library versions.

.. TODO: Do an example in S3

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

There is a :doc:`cli` as well. It can memoize UNIX or other commands from the
shell.

Extra State
-----------

Sometimes, language-level closures are not enough to track state. For this, the
user can supply ``memoize(..., extra_function_state=callable_obj)``. The return
value of ``callable_obj``. When it changes, then the cache for that function is
dropped. However, it is generally better to use ``__cache_key__`` and ``__cache_ver__``
rather than ``extra_function_state`` (see :doc:`How It Works`).

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
(useful for debugging). Unfortunately, Python's |hash|_ will return different
values across different runs, so I use :py:func:`~charmonium.cache.determ_hash`.

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
