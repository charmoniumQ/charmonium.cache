- Makefile targets depend on Makefile.
- FFI
- C-level I/O
- OOP
- Function determinism
- Functions that modify their arguments
- Security of unpickle arbitrary data.

Sharing the cache.

`IncPy` can also memoize pure functions across subsequent process invocations. However, `IncPy` has to modify the CPython interpreter in the following ways:

- TODO

`charmonium.cache` completes the same task with comparable overhead but as a library rather than a source-code fork of the interpreter. This yields two advantages:

- `charmonium.cache` easier to keep up-to-date with new versions of CPython than `IncPy`. In fact, `IncPy` was only developed for Python 2.6, which was obsolete in 2010.
- It provides a proof-of-concept that can be implemented in any other languages which supports:
  - Serialization and deserialization of the objects used as parameters and returns to functions.
  - Access to a checksum of the source-code of a function at runtime.
  - Function decorators
  - Reader-level macros, for automated application. A memoization library can be useful without automated application; in that case, the developer would need to add a decorator to each function they want to memoize. This is one line-of-code per function of interest, which in my examples, were usually 1 to 5 per project.
  - Access to the global closure of a function. This can be written in terms of the AST and access to the lexical namespace.

Parsl is a library primarily for parallel programming, but it happens to also have a memoization. However, its memoization only detects invalidation in the source code of the memoized function, not any called functions, and not any global variables. `charmonium.cache` handles both of these cases.

Joblib

functools.lru_cache

In addition to these theoretical
