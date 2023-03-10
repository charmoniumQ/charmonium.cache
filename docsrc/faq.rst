Frequently Asked Questions
==========================

Does X library do the same thing?
---------------------------------

See :ref:`Prior Work`.

In particular, does the library in question know to invalidate when your source
code changes? What if ``foo()`` calls ``bar()``, ``foo()`` is cached, and
``bar()`` changes?

Just use a workflow manager
---------------------------

Workflow managers help when you need to get a fresh copy of the results, but
they have a blind spot. lot of engineers practice *iterative development* where
small changes are common. Do you have to rerun a long-running task if one line
changes?

The better answer is: Use both. Workflow managers decide whether or not to run
your program. If they decide to run your program, ``charmonium.cache`` will
speed that up.

Does this work on instance methods?
-----------------------------------

Yes.

>>> from charmonium.cache import memoize
>>> class Class:
...     def __init__(self, y):
...         self.y = y
...     @memoize()
...     def foo(self, x):
...         print("Recomputing")
...         return x + self.y
... 
>>> obj = Class(3)
>>> obj.foo(4)
Recomputing
7
>>> obj.foo(4)
7
>>> obj.y = 5
>>> obj.foo(4)
Recomputing
9

Just make sure to put the ``@classmethod`` and ``@staticmethod`` *above* the ``@memoize()``, `as usual`_.

.. _`as usual`: https://stackoverflow.com/a/6208458/1078199

Does the cache detect changing something by inheritance?
--------------------------------------------------------

Yes.

.. code:: python

    class A:
        def foo(self):
            return 1
    class B(A):
        pass

    @memoize()
    def do_foo(obj):
        return obj.foo()

    print(do_foo(B())) # prints 1

.. code:: python

    ...

    class A:
        def foo(self):
            return 2

    ...

    print(do_foo(B())) # prints 2

This works because the library does not use the default language |hash|_. It uses
a comprehensive |charmonium.freeze|_, which takes into account the methods
attached to an object. Likewise, the cache will detect adding the method in the
child class.

.. code:: python

    ...

    class B(A):
        def foo(self):
            return 3

    ...

    print(do_foo(B())) # prints 3

Does the cache know about global variables?
-------------------------------------------

Yes.

>>> from charmonium.cache import memoize
>>> i = 0
>>> @memoize()
... def square(x):
...     return x**2 + i
... 
>>> print(square(4))
16
>>> i = 1
>>> print(square(4))
17

|charmonium.freeze|_ knows how to find the closure of the function ``square``, which
includes the global variables it refernces.


Does the cache know about reflection?
-------------------------------------

The cache is safe with respect to |getattr|_ reflection. This is because
|charmonium.freeze|_ hashes all of the attributes.

>>> from charmonium.cache import memoize
>>> @memoize()
... def get_x(obj):
...     return getattr(obj, "x")
... 
>>> class Struct:
...     pass
>>> obj = Struct()
>>> obj.x = 4
>>> get_x(obj)
4
>>> obj.x = 5
>>> get_x(obj)
5

However, the cache doesn't know about purely string-based reflection, like
``globals()["variable"]``. This is a useful escape hatch when you want the cache
to ignore something.

>>> from charmonium.cache import memoize
>>> @memoize()
... def get_x():
...     return globals()["x"]
... 
>>> x = 4
>>> get_x()
4
>>> x = 5
>>> get_x() # we get a stale result
4

How does the cache know about source-code changes in a C library?
-----------------------------------------------------------------

It doesn't. That is one of the shortcomings. However, in practice this is
probably ok. Most C libraries are not going to be changing frequently (projects
that use Numpy rarely change Numpy).

What about impure functions?
----------------------------

The library does its best to detect *language-level impurities*: that is,
modifying global variables. However, there exist *environmental impurities*:
``open(file).read()`` will be non-deterministic if the underlying file
changes. This library has a much harder time detecting this, but it should be
fairly obvious to the user when they write a non-deterministic function. Don't
cache those.

What about reading the filesystem or network?
---------------------------------------------

Unfortunately, this library can't tell if your function reads the filesystem or
network to get its result. If you still want to cache this function, see
:ref:`Capturing Filesystem Side-Effects`.

I'm working on a way of detecting this kind of impurity and warning the user, so
they don't get blindsided by stale results.

What about random number generators?
------------------------------------

The RNG state for builtin ``random`` and most other random number generators is
stored in a module-level global variable, which means the cache will know to
re-call the function.

>>> from charmonium.cache import memoize
>>> from random import randint, seed; seed(1)
>>> @memoize()
... def foo():
...     return randint(0, 10)
... 
>>> foo()
4
>>> foo()
1


I'm still not convinced this is safe for my particular use-case.
----------------------------------------------------------------

If you suspect the cache is returning stale results, you can disable it globally
with ``export CHARMONIUM_CACHE_DISABLE=1``. This makes it easy to tell if this
library is causing your problem.

This library is not invalidating when it should or invalidating when it shouldn't.
----------------------------------------------------------------------------------

You've found a bug. See :ref:`Debugging` if you want to debug this
yourself. Please file it on `GitHub`_, so I know about it.

.. _`GitHub`: https://github.com/charmoniumQ/charmonium.cache/issues/new

Isn't Pickle insecure?
----------------------

This library is un/pickling data that one of your dependent packages wrote. If
that dependent package was malicious, it could already execute arbitrary code on
your machine when you included it in your project. Using this library does not
increase your attack surface. Always vet your dependencies.

.. |hash| replace:: ``hash``
.. _`hash`: https://docs.python.org/3/library/functions.html?highlight=hash#hash
.. |charmonium.freeze| replace:: ``charmonium.freeze``
.. _`charmonium.freeze`: https://github.com/charmoniumQ/charmonium.freeze/
.. |getattr| replace:: ``getattr``
.. _`getattr`: https://docs.python.org/3/library/functions.html?highlight=getattr#getattr
