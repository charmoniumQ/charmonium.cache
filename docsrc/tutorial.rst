Tutorial
========

How to Use
----------

First you need to identify candidates for memoization.

- They should be *language-level* `pure`_. Global variables are ok, but
  system-level global state is not (e.g. setting ``os.environ``).

- File IO operations should be done through ``FileContents`` (see
  below). Alternatively, do the File IO in a wrapper function around a pure
  inner function.

- Likewise, The function and those it depends on should be relatively
  stable. This library can only safely use cached values over subsequent
  processes if the source code of those functions does not change.

- The function should have a high rate of reused arguments.

- The returned value should have a low data storage size.

- The function should have a long compute time, so memoization can save a lot of
  work.

Note that multiple functions are cached in the same backend store. This way, a
good candidate for memoization can "steal space" from bad candidates, as long as
the replacement policy is decent.

Once you have your candidate, simply add :py:func:`~charmonium.cache.memoize` to
the line above the function definition. Per-function customizations go inside
the parens. For example,

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

>>> from charmonium.cache import MemoizedGroup
>>> squared.group = MemoizedGroup(size="100KiB")

Extra State
-----------

Sometimes, language-level closures are not enough to track state. For this, the
user can supply ``memoize(..., extra_function_state=callable_obj)``. The return
value of ``callable_obj``. When it changes, then the cache for that function is
dropped. However, it is generally better to use ``__cache_key__`` and ``__cache_ver__``
rather than ``extra_function_state`` (see :ref:`Customizing Argument Keys`).

State can be added to the whole system by ``MemoizedGroup(...,
extra_system_state=callable_obj)``. The return value of ``callable_obj`` is a
part of the 1st match subkey. When it changes, the whole cache is dropped.

`Time-to-live`_ (TTL) is a common cache policy. For example, the memoized
function may be an API that you can call afresh every minute, but need to cache
it between those calls. TTL can easily be supported this way at either the
function or group-level by customizing ``extra_function_state`` and
``extra_system_state``. See :py:class:`~charmonium.cache.TTLInterval` for more
details.

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
        print("Doing copy")
        copy(src, dst)
        return dst

    # The first time, we have to run the function
    # This prints "Doing copy"
    pure_copy(FileContents("test"))

    # The second time (if the file hasn't changed on the disk),
    # @memoize emulates the file-system side-effects without running the function.
    # This will not print "Doing copy."
    pure_copy(FileContents("test"))

- :py:class:`~charmonium.cache.FileContents` has a custom hash function that
  includes a hash of its contents; if the ``src`` file changes, the hash
  changes, and `pure_copy` is rerun.

- :py:class:`~charmonium.cache.FileContents` has a custom de/serialization
  includes the contents; when the memoization of ``pure_copy`` misses, it will
  run the underlying ``copy`` and store the new contents of ``dst``. When
  memoization of ``pure_copy`` hits, it will deserialize those contents and
  write them into ``dst``, emulating the side-effect of ``copy``.

Usage in data pipelines
-----------------------

Naively, the entire input has to be hashed to retrieve or store a cached
result. This can be quite annoying, if your code operates on large dataframes or
numpy arrays. Instead, use a thunk which uniquely represents the data,

Suppose we have two functions:

.. code:: python

    def f(filename: str) -> pd.DataFrame:
        ...

    def g(df: pd.DataFrame) -> pd.DataFrame:
        ...

    df = f("filename")
    df = g(df)


We would write a memoization script like this:

.. code:: python

    from charmonium.cache import memoize

    @memoize()
    def f(filename: str) -> pd.DataFrame:
        ...

    # @memoizing g would have to hash the entire df.

    # If the filename uniquely determines the contents of the df
    # (e.g. the file is not changed between runs),
    # then ideally, we should just use the filename and f's source code as a key to the cache.
    # This can be done automatically by making new_g accept a "thunk" instead of accepting data.

    # The type annotation is optional, but I will include it for clarity.
    from typing import TypeVar, Generic
    T = TypeVar("T")
    class Thunk(Generic[T]):
        def __call__(self) -> T:
            ...

    @memoize()
    def g(df_thunk: Thunk[pd.DataFrame]) -> pd.DataFrame:
        df = df_thunk()
        ...
        return df

    import functools
    # This is essentially lazy evaluation of f.
    df_thunk = functools.partial(f, "filename"))
    df = g(df_thunk)
    # If f's source code does not change, f("filename") will be reused.
    # If f's and g's source code does not change, then g(df_thunk) will be reused.

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

        # Trim off output side-effects
        return ret[0]

    # New signature, old body
    @memoize()
    def _real_work(input1, input2, global_var):
        ...

        # Load up side-effects into an object.
        # The object will be serialized into the cache now and deserialized whenever the function is called.
        # Deserializing should "redo" the side effect.
        output_side_effect1 = FileContents("file_I_wrote.txt")

        # Append output side-effects
        return ret, output_side_effect1

Using in a distributed system
-----------------------------

The library can be used to reuse results *between* machines, but you must
satisfy some invariants:

- Use a de/serialization "pickler" that will work between the platforms in
  question. Consider OS, Python version, and library versions.

.. TODO: Do an example in S3

- Use an :py:class:`~charmonium.cache.ObjStore` that is accessible between the
  machines in question. :py:class:`~charmonium.cache.DirObjStore` is accessible
  between machines if you provide a :py:class:`~charmonium.cache.PathLike`
  object that is accessible between machines. For example, `Universal Pathlib`_
  provides a PathLike object representing an AWS S3 path or a GitHub path.

- The object store should support atomic concurrent accesses to the same key.

  - If there is a write-write race, it doesn't matter which one wins, as long as
    the write is atomic (not mangling together both writes). In theory, if all
    the functions are pure, the two written values should deserialize to the
    same object, although the binary representation may not be bit-equivalent.

  - If there is a read-write race, the reader should be able to see the value
    before the writer or after, but not during. In theory, if all the functions
    are pure, the pre-existing and newly-written value should deserialize to the
    same object, although the binary representation may not be bit-equivalent.

- Use an appropriate lock. Without a lock, one could loose data in the
  following. In the following example, even though ``f(1)`` and ``f(2)`` were
  both computed, only one will be remembered.

  .. list-table:: 
     :widths: auto
     :header-rows: 1
  
     * - Time
       - Index on disk
       - Machine 1
       - Machine 2
     * - T1
       - {}
       - compute f(1); local index = {1: f(1)}
       - compute f(2); local index = {2: f(2)}
     * - T2
       - {}
       - read and merge index; local index = {1: f(1)} merged with {}
       - 
     * - T3
       - {}
       - write index = {1: f(1)}
       - read and merge index; local index = {2: f(2)} merged with {}
     * - T4
       - {1: f(1)}
       - 
       - write index = {2: f(2)}
     * - T4
       - {2: f(2)}
       - 
       - 

  But with an appropriate lock,

  .. list-table:: 
     :widths: auto
     :header-rows: 1
  
     * - Time
       - Index on disk
       - Machine 1
       - Machine 2
     * - T1
       - {}
       - compute f(1); local index = {1: f(1)}
       - compute f(2); local index = {2: f(2)}
     * - T2
       - {}, locked by 1
       - read and merge index; local index = {1: f(1)} merged with {}
       - 
     * - T3
       - {}, locked by 1
       - write index = {1: f(1)}
       - 
     * - T4
       - {1: f(1)}
       - 
       - 
     * - T5
       - {1: f(1)}, locked by 2
       - 
       - read and merge index; local index = {1: f(1), 2: f(2)}
     * - T6
       - {1: f(1), 2: f(2)}
       - 
       - write index
     * - T7
       - {1: f(1), 2: f(2)}
       - 
       - 

- Consider setting fine-grain persistence
  (``@memoized(fine_grain_persistence=True)``). This writes the index after
  every successful function call, so a processes can reuse work done by a
  concurrent process. However, it will increase contention on the index lock.


Using the CLI
-------------

There is a :doc:`cli` as well. It can memoize UNIX or other commands from the
shell.

Debugging
---------

There are two classes of bugs:

- Data is loaded from the cache when it shouldn't be.

- Data isn't loaded from the cache when it should be. Generally this is more
  prevalent; the code is quite good at detecting source-code changes, provided all
  of the functions are pure.

1. In either case, Try and isolate the problem to a minimal example, 1 or 2 function calls that triggers the undesirable behavior.

2. Then, turn on logging.

   .. code:: python
   
       import logging, os
       logger = logging.getLogger("charmonium.cache.ops")
       logger.setLevel(logging.DEBUG)
       fh = logging.FileHandler("cache.log")
       fh.setLevel(logging.DEBUG)
       fh.setFormatter(logging.Formatter("%(message)s"))
       logger.addHandler(fh)
       logger.debug("Program %d", os.getpid())

3. When you run the script, you should see a file ``cache.log`` containing lines
   of JSON. Find the line containing ``"event": "hit"`` or ``"event:" "miss"``
   for where ``"name"`` is equal to the function you are trying to memoize. Look
   at the ``"obj_key"`` and ``"key"`` that the cache was trying to look up.

  ::

      Program 298881
      ...
      {"event": "miss", "call_id": 8476881272104231217, "name": "ascl_net_scraper.lib.scrape_index", "key": [["1.2.6"], "ascl_net_scraper.lib.scrape_index", 86185585044038137470190185817543203029, 174330435704821325504748322645885609728, 180438396020953764024835219690063154758], "obj_key": 204399087203688357111758696509623522761}
      ...

4. See `How It Works` for details ``"key"``; for now it will suffice to say it
   is a five-tuple containing the system state, function name, function state,
   arguments, and argument versions. These get hashed together to a single
   object key that the cache will associate with this result.

5. If this misses but you think it should hit, search up to find that object key
   in a prior run. There are three cases:

  - It was computed, but got deleted by ``"event": "evict"``. You ran out of
    space in the cache. This can be simply fixed by allocating a bigger one (see
    "Group-wide customization" in `How to Use`).

  - It was computed, but got deleted by ``"event": "cascading_delete"``. This
    can happen if there is a second call to the same function, but the function
    state changed, or if there was an ``"event": "index_read"`` which had a
    different function state.

    - If the function state changed, all old results may not be invalid. Let's
      figure out why the function state changed in the next step.

    - Index reads attempt to merge the index on disk with the index in RAM,
      resolving conflicts by deferring to whichever ``"version"`` is newer
      (greater). Let's figure out why in the next step.

  - It was never computed. If it was never computed, look for just the arguments
    (4th and 5th) element of ``"key"``. Perhaps the system changed between,
    which would in turn, cause the ``"obj_key"`` to change. Let's figure out why
    that would change in the next step.

6. If you are trying to figure out why a segment of the ``"key"`` takes a
   particular value, see the `debugging help in charmonium.freeze`_.

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
use_metadata_size=True)`` to include metadata in the size calculation. This is a
bit slower, so it is not the default.

By default, the cache is only culled to the desired size just before
serialization. To cull the cache after every store, set ``memoize(...,
fine_grain_eviction=True)``. This is useful if the cache would run out of memory
without an eviction.

Be aware of ``memoize(..., verbose=True|False)``. If verbose is enabled, the
cache will emit a report at process-exit saying how much time was saved. This is
useful to determine if caching is "worth it."

By default, I use the Greedy-Dual-Size Algorithm from [Cao et al.]_. This can be
customized by specifying ``memoize(replacement_policy=YourPolicy())`` where
``YourPolicy`` inherits from :py:class:`~charmonium.cache.ReplacementPolicy`.`

See :py:class:`~charmonium.cache.Memoized` and
:py:class:`~charmonium.cache.MemoizedGroup` for details.

.. _`time-to-live`: https://en.wikipedia.org/wiki/Time_to_live
.. _`pure`: https://en.wikipedia.org/wiki/Pure_function
.. _`Universal Pathlib`: https://github.com/Quansight/universal_pathlib
.. _`debugging help in charmonium.freeze`: https://github.com/charmoniumQ/charmonium.freeze/tree/main/README.rst#debugging
