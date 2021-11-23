=======
History
=======

While working on a data-intensive project, I wrote too much code like:

.. code:: python

    def do_task1():
        ...

    def get_cached_task1():
        ...

    try:
        result = get_cached_task1()
    except KeyError:
        result = do_task1()
		# store result somehow

Not only did this have lots of repetition, there came to be subtle bugs that
would only happen to some inputs, because the data loaded from cache had
slightly different properties (e.g. in-datastructure pointers) than the data
computed on the fly.

I wanted to unify the case where the results come from storage and abstract that
in a decorator. The earliest form of what is now this project was born:

.. code:: python

    def cache(f):
        cache_mem = read_from_disk()
        def cached_f(*args):
            if args in cache_mem:
                return cache_mem[args]
            else:
                result = f(*args)
                cache_mem[args] = result
                store_to_disk(cache_mem)
                return result

My project grew more sophisticated. I pulled ``cache`` out into its own class I
statically typed everything (before `PEP612`_/``ParamSpec`` was a glimmer in Guido's
eye). Since I was getting more serious about software design, I decided the
client should be able to use any storage backend, so long as it satisfied a
dict-like interface. Then I wrote an backend for Google Cloud Storage so that I
could use caching in my distributed system. This version still exists
`here`_. It worked like:

.. code:: python

    >>> @Cache.decor(DirectoryStore(GSPath.from_url("gs://blah/blah"))) # doctest: +SKIP
    ... def foo():
    ...     pass

.. _`PEP612`: https://www.python.org/dev/peps/pep-0612/
.. _`here`: https://github.com/charmoniumQ/EDGAR-research/blob/master/edgar_code/cache.py

It became so useful, that I decided to publish it as a PyPI package. This way I
could use it in future projects more easily. This was the 0.x release.

I didn't touch this code for a year, but I was using it for the data analysis
phase of my newest project, `ILLIXR`_. This was the first real test of my
software because it was the first time I know it had real users other than
me. When my cowoerkers were hacking on the data analysis, they would often tweak
a few lines rerun, and caching would unhelpfully provide a stale result, based
on the old verison of the code. This became such a problem that my coworkers
just deleted the cache every time they ran the code, making it worse than
useless.

.. _`ILLIXR`: https://illixr.github.io/

It would be really nice if I could detect when the user changes their code and
invalidate just that part of the cache. This is exactly what `IncPy`_ does, but
``IncPy`` is a dreaded *research project*. It hasn't been maintained in years,
only works for Python 2.6, and requires modifications to the interpreter. It
would be really nice if I could somehow detect code changes at the
*library-level* instead IncPy's approach of hacking the interpreter.

I started digging, and I realized that the facilities were already there in:
``function.__code__`` and |inspect.getclosurevars|! Then I knew I needed to
write a new release. This release became 2.x. I became much more acquainted with
Python development tools. I used better static typing (`PEP612`_) and wrote hella
unit tests.

.. _`IncPy`: https://dl.acm.org/doi/abs/10.1145/2001420.2001455
.. |inspect.getclosurevars| replace:: ``inspect.getclosurevars``
.. _`inspect.getclosurevars`: https://docs.python.org/3/library/inspect.html#inspect.getclosurevars
.. _`PEP612`: https://www.python.org/dev/peps/pep-0612/

This caching tool can be boon to data scientists working in Python. A lot of
people use this strategy of writing a data processing pipeline in stages, and
then they find they need to tweak some of the stages.

- Some people manually load/store intermediate results, which is time-consuming
  and error-prone. How do you know you didn't forget to invalidate something?

- People sometimes use Juypter Notebooks and keep the results around in RAM, but
  Jupyter Notebooks have their `detractors`_ and what if you need to restart the
  kernel for some reason?

.. _`detractors`: https://docs.google.com/presentation/d/1n2RlMdmv1p25Xy5thJUhkKGvjtV-dkAIsUXP-AL4ffI/edit#slide=id.g362da58057_0_1

Using my caching strategy, you can have the comfort of your IDE and the
appearance that you are rerunning the entire computation start-to-finish, but it
takes just the amount of time to recompute what changed.

Future work I have planned involves integrating more closely with existing
workflow managers like `dask`_ and `Parsl`_. If I can plug into a workflow
system people already use, I can lower the barrier to adoption.

I want to do some of the tricks that IncPy does, such as detecting impure
functions and automatically deciding which functions to cache. Then I want to do
performance comparisons to quantify the benefit and overhead.

.. _`dask`: https://dask.org/
.. _`Parsl`: https://parsl.readthedocs.io/
