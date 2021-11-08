============
How it works
============

The cache has two levels of indirection: an **index** and an
:py:class:`~charmonium.cache.ObjStore`.

1. The index maps **index keys** to **entries**. The keys are based on the
   function arguments among other things. Each entry holds metadata (frequency
   of use, size on disk) and an **object key**. The index datastructure is not
   user-customizable.

2. The **object store** maps **object keys** to an **object**. This object is
   the serialized return value of the function. The object store is
   user-customizable.

-----
Index
-----

The index key is a tuple of **subkeys**. The index is hierarchical on each
subkey (conceptually, ``index[subkey1][subkey2][subkey3]...``). Each subkey is
either a lookup or match subkey. During an insert, if a **lookup subkey** is not
found in the index, the subkey is *inserted beside* the non-matching subkeys. If
a **match subkey** is not found, the subkey *replaces* the old subkey.

This replacing behavior saves space when revisiting prior versions is rare. A
function's source-code is monotonic; there is little use in holding results form
a prior source-code version. While a healthy replacement policy may have evicted
the old version on its own if it is not used in the future, a match subkey
*guarantees* it gets evicted.

The index key has five subkeys:

1. The state of the system (match subkey): this includes the package version

2. The function name (lookup subkey): cache entries for different functions live
   in the same index but are separated at this index level.

3. The function version (match subkey): this includes the source-code,
   closure-state, and memoization configuration.
   
4. The function arguments (lookup subkey): this can be customized by
   ``arg.__cache_key__()`` but defaults to the object itself.

5. The function argument versions (match subkey): this can be
   customized by ``arg.__cache_ver__()``, but defaults to a constant.

The object key is a hash of the index key. If two parallel workers both try to
do the same computation (all five subkeys same), they will not store two copies
of the result. One will overwrite the other with identical contents.

The index is necessary because I want to be able to delete *all* of the objects
beneath a match subkey. For example, if the function contents change, I want to
delete all objects in ``index[state][function_name]``. I don't want to require
object store to have a fast "list objects beginning with this prefix" operation,
when the number of objects is O(1000). For example, Amazon S3 has no such
operation; having a Python dict-of-dicts is faster than iterating over all the
keys in an S3 bucket and checking their prefix.

Object Store
------------

The object store conforms to this interface:
:py:class:`~charmonium.cache.ObjStore`. That is, it maps 64-bit integer keys to
``bytes``.

:py:func:`~charmonium.cache.DirObjStore` will work with any storage backend
which emulates the |__pathlib__|_ interface. `Universal Pathlib`_ provides such
an interface for a variety of storage backends including Amazon S3.

Customizing Argument Keys
-------------------------

Some arguments might need to define their own notion of equality for the
purposes of memoization. These arguments should have a ``__cache_key__()``. It
can return anything that can be made hashable with
(:py:func:`~charmonium.cache.hashable`). As far as I know, every python object
can be made hashable with hashable. If ``__cache_key__()`` is not found, the
object itself is used as the key. This yields basic memoization.

Some arguments represent "versioned resources," in the sense that old versions
are not useful (rarely reused). In this case, ``__cache_key__()`` should return
the name of the resource and ``__cache__ver__()`` should return the version. If
``__cache_ver__()`` is not found, a constant is used.

If you can't modify the class, you can monkey-patch the object. See
:py:func:`~with_attr`.

.. code:: python

    obj = with_attr(obj, "__cache_key__", lambda: ...)

Detecting Changes in Functions
------------------------------

If any global variables (including other functions) referenced by the target
change, the cache is invalidated. I use a method similar but superior to
|inspect.getclosurevars|_ to read these.

.. code:: python

    >>> i = 42
    >>> def bar(x):
    ...     return x+1
    >>> def foo():
    ...     return bar(i)
    ... 
    >>> import inspect
    >>> inspect.getclosurevars(foo)
    ClosureVars(nonlocals={}, globals={'bar': <function bar at ...>, 'i': 42}, builtins={}, unbound=set())

To assess if a function has changed, I compare the closure-variables and the
compiled bytecode (e.g., ``foo.__code__.co_code``). See
:py:func:`~charmonium.cache.determ_hash` for more details.

.. _`Universal Pathlib`: https://github.com/Quansight/universal_pathlib
.. |pathlib| replace:: ``pathlib``
.. _`pathlib`: https://docs.python.org/3/library/pathlib.html
