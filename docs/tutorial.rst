Tutorial
========

Cache Functionality
-------------------

The cache is organized into an *index* and an *object store*. The index maps *keys* to
*entries*. Each entry (usually) holds an *object key* that maps to an *object* in the object
store. The *object* is the serialized return value of the function.

The key is a tuple of *subkeys*. The index is hierarchical on each subkey (a dict of dict of dicts
etc.). Each subkey is either a *lookup* or *match* subkey. During an insert, if a *lookup* subkey is
not found in the index, the subkey is inserted beside the non-matching subkeys. If a *match* subkey
is not found, the subkey **replaces** the old subkey.

This replacing behavior saves space when revisiting prior versions is rare. A function's source-code
is monotonic; there is little use in holding results form a prior source-code version. While a
healthy replacement policy may have evicted the old version on its own, a match subkey *guarantees*
it gets evicted.

The key has five subkeys:

1. The state of the system (match): this includes the package version
2. The function name (lookup)
3. The function version (match): this includes the source-code, closure-state, and memoization configuration
4. The arguments (lookup): this can be customized by ``__cache_key__()`` but defaults to the object itself.
5. The argument versions (match): this can be customized by ``__cache_ver__()``, but defaults to a constant.

Different functions share a backend index and function store, and we will see why in a moment.

How to Use
----------

First you need to identify candidates for memoization.

- They should be *mostly* `pure`_. The library is correct in the presence of global variables, if
  they change frequently, it will degrade performance.

- Likewise, The function and those it depends on should be relatively stable.

- The function should have a high rate of reused arguments.

- The returned value should have a low data storage size. You can customize the returned object with
  |__getstate__|_.

- The function should have a long compute time, so memoization can save a lot of work.

Note that multiple functions are cached in the same backend store. This way, a good candidate for
memoization can "steal space" from bad candidates, as long as the replacement policy is decent.

Once you have your candidate, simply add |@memoize()|_ to the line above the function
definition. Per-function customizations go inside the parens. For example,

.. code:: python

    >>> from charmonium.cache import memoize
    >>> @memoize()
    ... def square(x):
    ...     print(f"squaring {x}")
    ...     return x**2
    ... 
    >>> square(2)
    squaring 2
    4
    >>> square(2)
    4

Group-wide customizations are applied after definition. For example, size is applied like:

.. code:: python

    >>> from charmonium.cache import MemoizedGroup
    >>> square.group = MemoizedGroup(size="100KiB")

Customizing Argument Keys
-------------------------

Some arguments might need to define their own notion of equality for the purposes of
memoization. These arguments should have a ``__cache_key__()``. It can return anything that can be
made hashable with (|hashable|_). As far as I know, every python object can be made hashable with
|hashable|_. If ``__cache_key__()`` is not found, the object itself is used as the key. This yields
basic memoization.

Some arguments represent "versioned resources," in the sense that old versions are not useful
(rarely reused). In this case, ``__cache_key__()`` should return the name of the resource and
``__cache__ver__()`` should return the version. If ``__cache_ver__()`` is not found, a constant is
used. If the version changes, then the older version is replaced rather than appended to.

Capturing Filesystem Side-Effects
---------------------------------

Sadly, not all code is pure; many times, legacy code has impure side effects on the filesystem. To
make legacy code memoizable, the library has a |FileContents|_ helper. This class represents a
filepath **and its contents**. ``fc.__cache_key__()`` returns the path while ``fc.__cache_ver__()``
returns the contents. Furthemore, ``pickle.dumps(fc)`` dumps a snapshot of the contents, while
``pickle.loads(fc_ser)`` restores those contents.

Suppose we have the following impure function:

.. code:: python

    def copy(src: str) -> None:
        with open(src, "rb") as src_f:
            result = long_function(src_f.read())
        with open(src + "_copy", "wb") as dst_f:
            dst_f.write(result)

We can convert this to a pure function by:

.. code:: python

    @memoize()
    def pure_copy(src: FileContents, dst: str) -> FileContents:
        copy(src, dst)
        return dst

This can be cached. If you give a ``src`` with the same path and same contents, then the output will
be recalled instead of computed (``long_function`` need not be called).

See |FileContents|_ for more details.

Detecting Changes in Functions
------------------------------

If any global variables (including other functions) referenced by the target change, the cache is
invalidated. I use |inspect.getclosurevars|_ to read these.

.. code:: python

    >>> i = 42
    >>> def bar(x):
    ...     return x+1
    >>> def foo():
    ...     return bar(i)

    >>> import inspect
    >>> inspect.getclosurevars(foo)
    ClosureVars(nonlocals={}, globals={'bar': <function bar at ...>, 'i': 42}, builtins={}, unbound=set())

To assess if a function has changed, I compare the closure-variables and the compiled bytecode
(e.g., ``foo.__code__.co_code``). See |determ_hash|_ for more details.

Using in the Cloud
------------------

TODO: this

- Fine-grain persistence, cloud storage path, lock

Using the CLI
-------------

There is a |CLI|_ as well. It can memoize UNIX or other commands from the shell.

Extra State
-----------

Sometimes, language-level closures are not enough to track state. For this, the user can supply
``memoize(..., extra_function_state=callable_obj)``. The return value of ``callable_obj`` is a part
of the 3rd match subkey. When it changes, then the cache for that function is dropped.

State can be added to the whole system by ``MemoizedGroup(...,
extra_system_state=callable_obj)``. The return value of ``callable_obj`` is a part of the 1st match
subkey. When it changes, the whole cache is dropped.

`Time-to-live (TTL)`_ is a common cache policy. For example, the memoized function may be an API
that you can call afresh every minute, but need to cache it between those calls. TTL can easily be
supported this way at either the function or group-level by customizing ``extra_function_state`` and
``extra_system_state``. See |TTLInterval|_ for more details.

Customizing Behavior
--------------------

See |Memoized|_ and |MemoizedGroup|_ for details.

.. _`time-to-live (TTL)`: https://en.wikipedia.org/wiki/Time_to_live
.. _`pure`: https://en.wikipedia.org/wiki/Pure_function
.. _`API reference`: http://example.com
.. |inspect.getclosurevars| replace:: ``inspect.getclosurevars``
.. _`inspect.getclosurevars`: https://docs.python.org/3/library/inspect.html#inspect.getclosurevars
.. |__getstate__| replace:: ``__getstate__``
.. _`__getstate__`: https://docs.python.org/3/library/pickle.html#object.__getstate__
.. |FileContents| replace:: ``FileContents``
.. _`FileContents`: http://example.com
.. |hashable| replace:: ``hashable``
.. _`hashable`: http://example.com
.. |TTLInterval| replace:: ``TTLInterval``
.. _`TTLInterval`: http://example.com
.. |determ_hash| replace:: ``determ_hash``
.. _`determ_hash`: http://example.com
.. |@memoize()| replace:: ``@memoize``
.. _`@memoize()`: http://example.com
.. |Memoized| replace:: ``Memoized``
.. _`Memoized`: http://example.com
.. |MemoizedGroup| replace:: ``MemoizedGroup``
.. _`MemoizedGroup`: http://example.com
.. |CLI| replace:: ``CLI``
.. _`CLI`: http://example.com
.. TODO API URLs
