Plans
-----

Design decisions:

- Use directory trees for fast dropping? No, not all FS support efficiently; Probably faster on avg to use an index file.

TODO:

- Use index versions to elide load

Goals achieved
--------------

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

    >>> @memoize() # this is the only line I have to add
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

    >>> @memoize()
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

