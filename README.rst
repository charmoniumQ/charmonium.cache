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
of time every run.

Quickstart
----------

If you don't have ``pip`` installed, see the `pip install
guide`_. Then run:

::

    $ pip install charmonium.cache

.. code:: python

    >>> from charmonium.cache import memoize
    >>> i = 0
    >>> @memoize()
    ... def square(x):
    ...     print("recomputing")
    ...     return x**2 + i
    ...
    >>> square(4)
    recomputing
    16
    >>> square(4)
    16
    >>> i = 2
    >>> square(4)
    recomputing
    17

The function must be pure with respect to its arguments and its `closure`_ (``i``
part of the closure in the previous example). This library will not detect:

- Reading **directly** from the filesystem (this library offers a wrapper over files
  that permits it to detect changes; use that instead).

- Non-static references (the caching library can't detect a dependency if the
  function references ``globals()["i"]``).

Advantages
----------

While there are other libraries and techniques for memoization, I believe this
one is unique because it is:

1. **Correct with respect to source-code changes:** The cache detects if you
   edit the source code or change a file which the program reads (provided they
   use this library's right file abstraction). Users never need to manually
   invalidate the cache, so long as the functions are pure.

2. **Useful between runs and across machines:** A cache can be shared on the
   network, so that if *any* machine has computed the function for the same
   source-source and arguments, this value can be reused by *any other* machine.

3. **Easy to adopt:** Only requires adding one line (decorator) to the function
   definition.

4. **Bounded in size:** The cache won't take up too much space.

5. **Shared for multiple functions:** The functions for which memoization has
   the best "bang for the buck" will take space from functions with a worse
   tradeoff.

6. **Supports smart heuristics:** They can take into account time-to-recompute
   and storage-size in addition to recency, unlike naive `LRU`_.

7. **Overhead aware:** The library measures the time saved versus overhead. It
   warns the user if the overhead of caching is not worth it.

CLI
---

::
   memoize [--obj-store path] [--env env] [--key key] [--ver ver] [--comparison (mtim|crc32)] [--replacement (gd-size|luv)] [--max-size '123 MiB'] [--verbose] -- command arg1 arg2 ...

``memoize`` memoizes ``command arg1 arg2 ...``. If the command, its arguments,
 or its input files change, then ``command arg1 arg2 ...`` will be
 rerun. Otherwise, the output files (including stderr and stdout) will be
 produced from a prior run.

Unlike GNU Make, the 

``command`` may require stdin, but no TTY interactivity.

``memoize`` uses ``strace`` to learn the input and output files.

The following items are matched in order. If any item is not found, then the
rest do not need to be checked; the cache needs to be refreshed. If a
key-to-check is not matched, then the prior entry is *deleted*. If a
key-to-lookup is not matched, the prior entry *co-exists* beside the newer
entry. key-to-check helps cull the cache early.

1. The ``--obj-store`` (implicitly) forms a key-to-lookup.
2. The ``--env`` forms a key-to-check.
3. The ``command`` form a key-to-lookup.
4. The contents of ``command`` is a key-to-check.
5. ``arg1, arg2, ...`` and ``--key`` form a key-to-lookup.
6. The input files and ``--ver`` form a key-to-check.

This is useful for ``memoizing`` parts of a shell-script pipeline. It can be
safely used in a pipe.

Code quality
------------

- The code base is strictly and statically typed with `pyright`_. I export type
  annotations in accordance with `PEP 561`_; clients will benefit from the type
  annotations in this library.

- I have unittests with >95% coverage.

- I use pylint with few disabled warnings.

- All of the above methods are incorporated into per-commit continuous-testing
  and required for merging with the ``main`` branch; This way they won't be
  easily forgotten.

- I've implemented the complete feature-set in only 700 LoC. LoC count is an
  imperfect but reasonable metric of how hard something is to maintain and how
  likely it is to contain bugs according to [Zhang]_.

Works Cited
-----------

.. [Guo] Guo, Philip Jia. *Software tools to facilitate research programming*. Stanford University, 2012. See Chapter 5. https://purl.stanford.edu/mb510fs4943
.. [Podlipnig] Podlipnig, Stefan, and Laszlo Böszörmenyi. "A survey of web cache replacement strategies." *ACM Computing Surveys (CSUR) 35.4* (2003): 374-398. http://www.cs.ucf.edu/~dcm/Teaching/COT4810-Fall%202012/Literature/WebCacheReplacementStrategies.pdf
.. [Zhang] Zhang, Hongyu. "An investigation of the relationships between lines of code and defects." *2009 IEEE International Conference on Software Maintenance*. IEEE, 2009. https://www.researchgate.net/profile/Hongyu-Zhang-46/publication/316922118_An_Investigation_of_the_Relationships_between_Lines_of_Code_and_Defects/links/591e31e1a6fdcc233fceb563/An-Investigation-of-the-Relationships-between-Lines-of-Code-and-Defects.pdf
.. .. [Bahn] Bahn, Hyokyung, et al. "Efficient replacement of nonuniform objects in web caches." *Computer* 35.6 (2002): 65-73. https://8cc2ce98-a-f3569e9e-s-sites.googlegroups.com/a/necsst.ce.hongik.ac.kr/publication/jalyosil/getPDF3.pdf?attachauth=ANoY7cqOpLmcb_3TXLj9ACr1qQojQMNL2eTEpG_q5kZXKjl3C6XcW4J0HIA8-ncTm5s0gBFJSK08Ju-on-O5Fu44GHhlOzaIzNkdCV-NaSCZhDpWBOiqJ7FjETvER92tnjJRuDtfRznLahZ7BJ4x2o6lliM00z22ZcAfL8TUVsy9sltZ_CX5WA28Dj2U647XrBjI8xv73GjIKC77J0ubdNuzTIQVDpf16nbqq0RUHzST0EupaNDlNR0%3D&attredirects=0
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
