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
    >>> import shutil; shutil.rmtree(".cache")
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
    >>> i = 1
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

3. **Easy to adopt:** Only requires adding one line (`decorator`_) to
   the function definition.

4. **Bounded in size:** The cache won't take up too much space. This
   space is partitioned across all memoized functions according to the
   heuristic.

5. **Supports smart heuristics:** They can take into account time-to-recompute
   and storage-size in addition to recency, unlike naive `LRU`_.

6. **Overhead aware:** The library measures the time saved versus overhead. It
   warns the user if the overhead of caching is not worth it.

CLI
---

::

   memoize -- command arg1 arg2 ...

``memoize`` memoizes ``command arg1 arg2 ...``. If the command, its arguments,
 or its input files change, then ``command arg1 arg2 ...`` will be
 rerun. Otherwise, the output files (including stderr and stdout) will be
 produced from a prior run.

Make is good, but it has a hard time with dependencies that are not files. Many
dependencies are not well-contained in files. For example, you may want
recompute some command every time some status command returns a different value.

::

    # make status=$(status) will not do the right thing.
    make var=1
    make var=2 # usually, nothing recompiles here, contrary to user's intent

    # memoize --key=$(status) -- command args will do the right thing
    memoize --key=1 -- command args
    memoize --key=2 -- command args # key changed, command is recomptued.

``memoize`` also makes it easy to memoize commands within existing shell scripts.

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

- I've implemented the complete feature-set in under 1,000 LoC. LoC
  count is an imperfect but reasonable metric of how hard something is
  to maintain and how likely it is to contain bugs according to
  [Zhang]_.

.. _`PEP 561`: https://www.python.org/dev/peps/pep-0561/
.. _`LRU`: https://en.wikipedia.org/wiki/Cache_replacement_policies#Least_recently_used_(LRU)
.. _`closure`: https://en.wikipedia.org/wiki/Closure_(computer_programming)
.. _`decorator`: https://en.wikipedia.org/wiki/Python_syntax_and_semantics#Decorators
.. _`pip install guide`: https://pip.pypa.io/en/latest/installing/
.. _`pyright`: https://github.com/microsoft/pyright
