# First release

- [x] Implement helpers:
  - [x] FileContents helper
  - [x] TTL helper
- [x] Use tox to test multiple environments.
- [x] Write documentation
  - [x] Write tutorial.
  - [x] Clean up theory.
- [x] Make memoization Thread safety.
- [x] Make `MemoizedGroup` picklable.
- [x] Fix `determ_hash(numpy.inte64(1234))`
- [x] Test usage in parallel environments.
- [x] Fix `time_cost` overreporting bug.
- [x] Test that Memoized functions compose.
  - Write `__determ_hash__` for `Memoized`.

# Bug fix release

- [x] Test for repeated use of multiprocessing
  - `setstate` clears version and reads cache
- [x] Test for `f(x)`, write, read, `f.would_hit(x)`.
  - `Index.__setitem__` doesn't delete if `last_level[last_key] = val`.
- [x] Content address object store or use hash(index keys)
  - This makes the object-key deterministic, so if two parallel workers compute the same object, only one gets stored.
  - Requires writes to be atomic
- [x] Make remove orphans optional.
- [x] Ensure validity when key is found in `index` but not in `obj_store`.
- [x] Print log on {invalidation, eviction, orphan, miss, hit}
  - [x] Handle long arg message
- [x] `determ_hash`  should use `xxHash`.
- [x] Improve determ_hash
  - [x] Catch Pickle TypeError
  - [x] Catch Pickle ImportError
- [x] Make `hashable` handle more types:
  - [x] Module: hash by name.
  - [x] Objects: include the source-code of methods.
  - [x] C extensions. hashed by name, like module
  - [x] Methods
  - [x] fastpath for numpy arrays

# Research tasks

- Fix hashing
  - [x] Bring hash into separate package.
  - [x] Test hashing sets with different orders. Assert tests fail.
  - [x] Test hashing dicts with different orders. Assert tests fail.
  - [ ] Test hash for objects and classes more carefully.
  - [x] Don't include properties in hash.
  - [ ] Support closures which include `import x` and `from x import y`
  - [x] Use user-customizable multidispatch.
  - [x] Make it work with `tqdm`.
- [x] Show which part of the key is invalidated
- Performance evaluation
  - [x] Macrobenchmark on commit history of real repositories.
  - [x] Microbenchmark
    - per Memoized: n misses, n hits, size of objects, hashing, deserialization, serialization, object load, object store, function, total on hit, total on miss
    - per MemoizedGroup: index load, index store, index size
- [ ] Integrate with Parsl.
  - [ ] Resp to comment [parsl comment]
- [ ] Documentation
  - [ ] Explain how to use logging (ops, perf, freeze).
  - [ ] Write about how memoization interacts with OOP.
  - [ ] Write about when memoization is unsound.
  - [ ] Record demo, update presentation, link presentation.
- [ ] Pull callgraph out into a library.
- Detect impurities
  - [ ] Compare global vars and fn arguments before and after running function.
  - [ ] Listen for [audit events].
  - [ ] Scan for references to non-deterministic functions (time, random, sys, os, path).
- [ ] Convert Jupyter Notebooks into scripts.
- [ ] Memoize the hash of pure functions.
- [ ] Make all packages in `site_packages` be assumed constant.
- [ ] Apply automatically using [importhook].
  - [ ] Write `maybe_memoize`.
  - [ ] Global config.
- [ ] Do writing-to-disk off the critical path, in a thread.

[audit events]: https://docs.python.org/3/library/audit_events.html#audit-events
[importhook]: https://brettlangdon.github.io/importhook/
[parsl comment]: https://github.com/Parsl/parsl/issues/1591#issuecomment-954863242

# IPython caching
- [ ] https://stackoverflow.com/questions/31255894/how-to-cache-in-ipython-notebook

# Minor release

- [ ] Encapsulate global config `freeze` into object.
- [ ] Improve the UX for setting MemoizedGroup options.
- [ ] Do `fsync` before/after load?
- [ ] Do I really need `memoize(..., temporary: bool = False)` in tests?
- [ ] Simplify `tests/test_memoize_parallel.py`.
- [ ] Shortcut for caching a decorator
- [ ] Support out-of-band (zero-copy) pickle-hashing in `determ_hash`.
- [ ] file-IO based pickle
- [ ] Make `fine_grain*` apply to a `Memoized` level. All benefit from positive externalities.
- [ ] Make resistant to errors.
  - Add `commit()`.
  - Use`sys.excepthook`.
- [ ] Optionally repay stdout on cache hit.
- [ ] Print usage report at the end, with human timedeltas.
- [ ] Use `poetry2nix`.
- [x] Replace `shell.nix` with `flake.nix`.

# Low priorities

- Regarding logs,
  - [ ] Humanize timedeltas.
- [ ] Reset stats
- [x] Implement GitHub actions.
  - [ ] Use code quality/anlaysis services (codacy, codeclimate, coverity, coveralls, sonarqube).
  - [ ] Upload coverage in CI.
- [ ] Add "button" images to README.
  - [ ] GitHub Actions checks
  - [ ] External code quality/analysis
- [ ] `hashable` prints log on error
- [ ] Make working example of caching in S3.
- [ ] Set up git-changelog.
- [ ] Make it work for instance methods.
- [ ] Make `charmonium._time_block` serializable
- [ ] Write about replacing notebooks.
