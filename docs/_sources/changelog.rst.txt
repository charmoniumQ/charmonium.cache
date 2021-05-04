Changelog
=========

1.1.0 (2021-05-07)
------------------

- ``MemoizedGroup`` is now picklable. This makes it usable by multiprocessing-based parallelism.
- ``Memoized`` and ``MemoizedGroup`` are now thread-safe.
- Improved log messages.
- ``determ_hash(obj)`` uses a hash of the ``pickle.dumps``. This makes it accept more datatypes such as ``numpy.int64``, which could not be hashed by the old ``determ_hash``. ``determ_hash`` still falls back to hashing-by-attributes for non-picklable objects.
- The ``time_cost`` used to over-estimate (include the time which would have been spent in the non-memoized case as well (recomputing f(x))).
- Tweaked documentation.
- ``with_attr(..., "key", lambda: key)`` replaces ``KeyVer(key, ver)``.

1.0.0 (2021-05-02)
------------------

- Initial public release
