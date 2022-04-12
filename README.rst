==========================
charmonium.cache
==========================

.. image:: https://img.shields.io/pypi/v/charmonium.cache
   :alt: PyPI Package
   :target: https://pypi.org/project/charmonium.cache
.. image:: https://img.shields.io/pypi/dm/charmonium.cache
   :alt: PyPI Downloads
   :target: https://pypi.org/project/charmonium.cache
.. image:: https://img.shields.io/pypi/l/charmonium.cache
   :alt: PyPI License
   :target: https://github.com/charmoniumQ/charmonium.cache/blob/main/LICENSE
.. image:: https://img.shields.io/pypi/pyversions/charmonium.cache
   :alt: Python Versions
   :target: https://pypi.org/project/charmonium.cache
.. image:: https://img.shields.io/github/stars/charmoniumQ/charmonium.cache?style=social
   :alt: GitHub stars
   :target: https://github.com/charmoniumQ/charmonium.cache
.. image:: https://github.com/charmoniumQ/charmonium.cache/actions/workflows/main.yaml/badge.svg
   :alt: CI status
   :target: https://github.com/charmoniumQ/charmonium.cache/actions/workflows/main.yaml
.. image:: https://codecov.io/gh/charmoniumQ/charmonium.cache/branch/main/graph/badge.svg?token=JTL4SNMWTP
   :alt: Code Coverage
   :target: https://codecov.io/gh/charmoniumQ/charmonium.cache
.. image:: https://img.shields.io/github/last-commit/charmoniumQ/charmonium.determ_hash
   :alt: GitHub last commit
   :target: https://github.com/charmoniumQ/charmonium.cache/commits
.. image:: https://img.shields.io/librariesio/sourcerank/pypi/charmonium.cache
   :alt: libraries.io sourcerank
   :target: https://libraries.io/pypi/charmonium.cache
.. image:: https://img.shields.io/badge/docs-yes-success
   :alt: Documentation link
   :target: https://charmoniumq.github.io/charmonium.cache/
.. image:: http://www.mypy-lang.org/static/mypy_badge.svg
   :target: https://mypy.readthedocs.io/en/stable/
   :alt: Checked with Mypy
.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
   :alt: Code style: black

Provides a decorator for caching a function between subsequent processes.

Whenever the function is called with the same arguments, the result is
loaded from the cache instead of computed. This cache is **persistent
across runs**. If the arguments, source code, or enclosing environment
have changed, the cache recomputes the data transparently (**no need
for manual invalidation**).

The use case is meant for iterative development, especially on scientific
experiments. Many times a developer will tweak some of the code but not
all. Often, reusing intermediate results saves a significant amount of time
every run.

See full documentation `here`_.

.. _`here`: https://charmoniumq.github.io/charmonium.cache/


Quickstart
----------

If you don't have ``pip`` installed, see the `pip install
guide`_.

.. _`pip install guide`: https://pip.pypa.io/en/latest/installing/

.. code-block:: console

    $ pip install charmonium.cache

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

5. **Supports smart heuristics:** By default, the library uses state-of-the-art
   cache policies that can take into account time-to-recompute and storage-size
   in addition to recency, more advanced than simple `LRU`_.

6. **Overhead aware:** The library measures the time saved versus overhead. It
   warns the user if the overhead of caching is not worth it.

.. _`Detecting Changes in Functions`: https://charmoniumq.github.io/charmonium.cache/tutorial.html#detecting-changes-in-functions
.. _`Klepto`: https://klepto.readthedocs.io/en/latest/
.. _`joblib.Memory`: https://joblib.readthedocs.io/en/latest/memory.html
.. _`functools.lru_cache`: https://docs.python.org/3/library/functools.html#functools.lru_cache
.. _`decorator`: https://docs.python.org/3/glossary.html#term-decorator
.. _`LRU`: https://en.wikipedia.org/wiki/Cache_replacement_policies#Least_recently_used_(LRU)

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
   memoize --key=$(date +%Y-%m-%d) -- command arg1 arg2

See `CLI`_ for more details.

.. _`CLI`: https://charmoniumq.github.io/charmonium.cache/cli.html
