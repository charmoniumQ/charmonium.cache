================
charmonium.cache
================

.. image: https://img.shields.io/pypi/dm/charmonium.cache
   :alt: PyPI Downloads
.. image: https://img.shields.io/pypi/l/charmonium.cache
   :alt: PyPI Downloads
.. image: https://img.shields.io/pypi/pyversions/charmonium.cache
   :alt: Python versions
.. image: https://img.shields.io/github/stars/charmoniumQ/charmonium.cache?style=social
   :alt: GitHub stars
.. image: https://img.shields.io/librariesio/sourcerank/pypi/charmonium.cache
   :alt: libraries.io sourcerank

- `PyPI`_
- `GitHub`_
- `Docs`_

Provides a decorator for caching a function. Whenever the function is called
with the same arguments, the result is loaded from the cache instead of
computed. This cache is **persistent across runs**. If the arguments, source
code, or enclosing environment have changed, the cache recomputes the data
transparently (**no need for manual invalidation**).

The use case is meant for iterative development, especially on scientific
experiments. Many times a developer will tweak some of the code but not
all. Often, reusing intermediate results saves a significant amount of time
every run.

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
    ...     # Imagine a more expensive computation here.
    ...     return x**2 + i
    ...
    >>> square(4)
    recomputing
    16
    >>> square(4) # no need to recompute
    16
    >>> i = 1
    >>> square(4) # global i changed; must recompute
    recomputing
    17

Advantages
----------

While there are other libraries and techniques for memoization, I believe this
one is unique because it is:

1. **Correct with respect to source-code changes:** The cache detects if you
   edit the source code or change a file which the program reads (provided they
   use this library's right file abstraction). Users never need to manually
   invalidate the cache, so long as the functions are pure (unlike
   `joblib.Memory`_, `Klepto`_).

   It is precise enough that it will ignore changes in unrelated functions in
   the file, but it will detect changes in relevant functions in other files. It
   even detects changes in global variables (as in the example above). See
   `Detecting Changes in Functions`_ for details.

2. **Useful between runs and across machines:** The cache can persist on the
   disk (unlike `functools.lru_cache`_). Moreover, a cache can be shared on the
   network, so that if *any* machine has computed the function for the same
   source-source and arguments, this value can be reused by *any other* machine,
   provided your datatype is de/serializable on those platforms.

3. **Easy to adopt:** Only requires adding one line (`decorator`_) to
   the function definition.

4. **Bounded in size:** The cache won't take up too much space. This
   space is partitioned across all memoized functions according to the
   heuristic.

5. **Supports smart heuristics:** Motivated by academic literature, I use cache
   policies that can take into account time-to-recompute and storage-size in
   addition to recency, unlike `LRU`_.

6. **Overhead aware:** The library measures the time saved versus overhead. It
   warns the user if the overhead of caching is not worth it.

Memoize CLI
-----------

Make is good for compiling code, but falls short for data science. To get
correct results, you have to incorporate *every* variable your result depends on
into a file or part of the filename. If you put it in a file, you only have one
version cached at a time; if you put it in the filename, you have to squeeze the
variable into a short string. In either case, stale results will accumulate
unboundedly, until you run ``make clean`` which also purges the fresh
results. Finally, it is a significant effor to rewrite shell scripts in make.

``memoize`` makes it easy to memoize steps in shell scripts, correctly. Just add
``memoize`` to the start of the line. If the command, its arguments,
or its input files change, then ``command arg1 arg2 ...`` will be
rerun. Otherwise, the output files (including stderr and stdout) will be
produced from a prior run. ``memoize`` uses ptrace to automatically determine
what inputs you depend on and what outputs you produce.

::

   memoize command arg1 arg2
   # or
   memoize --key=key -- command arg1 arg2

See `CLI`_ for more details.

.. _`PEP 561`: https://www.python.org/dev/peps/pep-0561/
.. _`LRU`: https://en.wikipedia.org/wiki/Cache_replacement_policies#Least_recently_used_(LRU)
.. _`closure`: https://en.wikipedia.org/wiki/Closure_(computer_programming)
.. _`decorator`: https://en.wikipedia.org/wiki/Python_syntax_and_semantics#Decorators
.. _`pip install guide`: https://pip.pypa.io/en/latest/installing/
.. _`pyright`: https://github.com/microsoft/pyright
.. _`PyPI`: https://pypi.org/project/charmonium.cache/
.. _`GitHub`: https://github.com/charmoniumQ/charmonium.cache
.. _`docs`: https://charmoniumq.github.io/charmonium.cache/
.. _`Detecting Changes in Functions`: https://charmoniumq.github.io/charmonium.cache/tutorial.html#detecting-changes-in-functions
.. _`Klepto`: https://klepto.readthedocs.io/en/latest/
.. _`joblib.Memory`: https://joblib.readthedocs.io/en/latest/memory.html
.. _`functools.lru_cache`: https://docs.python.org/3/library/functools.html#functools.lru_cache
.. _`CLI`: https://charmoniumq.github.io/charmonium.cache/cli.html
