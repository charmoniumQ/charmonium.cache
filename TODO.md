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

# Research tasks

- [x] Show which part of the key is invalidated
- Performance evaluation
  - [x] Macrobenchmark on commit history of real repositories.
  - [x] Microbenchmark
    - per Memoized: n misses, n hits, size of objects, hashing, deserialization, serialization, object load, object store, function, total on hit, total on miss
    - per MemoizedGroup: index load, index store, index size
- [ ] Integrate with Parsl.
  - [ ] Resp to comment [parsl comment]
- [ ] Documentation
  - [x] Explain how to use logging (ops, perf, freeze).
  - [ ] Write about how memoization interacts with OOP.
  - [ ] Write about when memoization is unsound.
  - [ ] Record demo, update presentation, link presentation.
- [ ] Pull callgraph out into a library.
- Detect impurities
  - [ ] Compare global vars and fn arguments before and after running function.
  - [ ] Listen for [audit events].
  - [ ] Scan for references to non-deterministic functions (time, random, sys, os, path).
- [x] Convert Jupyter Notebooks into scripts.
- [ ] The outputs of a cached function can be hashed by their progenesis.
- [ ] Make all packages in stdlib be assumed constant.
- [ ] Apply automatically using [importhook].
  - [ ] Write `maybe_memoize`.
  - [ ] Global config.
- [ ] Do writing-to-disk off the critical path, in a thread.
- [ ] Create a better API for group configuration.
- [ ] Write about variable name ambiguity.
- [ ] See if [lazy_python] could be of use.
- [ ] Cache should hit if entry is absent in index but present in obj store ("recover" orphans). In this case, we have the result, but not the metadata. Just create the metadata on the spot and use the computed result.
- [ ] Test fine-grained persistence more carefully.

[audit events]: https://docs.python.org/3/library/audit_events.html#audit-events
[importhook]: https://brettlangdon.github.io/importhook/
[parsl comment]: https://github.com/Parsl/parsl/issues/1591#issuecomment-954863242
[lazy_python]: https://pypi.org/project/lazy_python/

# Minor release
- [ ] Use environment variable to specify cache location.
- [ ] Improve test coverage in charmonium.cache, charmonium.determ_hash
- [ ] Improve the UX for setting MemoizedGroup options.
- [ ] Have an option for `system_wide_cache` that stores the cache directory in a deterministic (not relative to `$PWD`) path.
- [ ] Do `fsync` before/after load?
- [ ] Do I really need `memoize(..., temporary: bool = False)` in tests?
- [ ] Simplify `tests/test_memoize_parallel.py`.
- [ ] Shortcut for caching a decorator
- [ ] file-IO based pickle
- [ ] Make `fine_grain*` apply to a `Memoized` level. All benefit from positive externalities.
  - There is an argument against this. A user could puprosefully make a low-frequency call fine-grained but not a high-frequency call. This would reduce contention while still providing a checkpoint wihtin the program.
- [ ] Make resistant to errors.
  - Add `commit()`.
  - Use`sys.excepthook`.
- [ ] Optionally repay stdout (and logs?) on cache hit.
- [ ] Make sure adding a loghandler doesn't invalidate cache.
- [ ] Print usage report at the end, with human timedeltas.
- [x] Replace `shell.nix` with `flake.nix`.

# Low priorities

- [ ] https://stackoverflow.com/questions/31255894/how-to-cache-in-ipython-notebook
- Regarding logs,
  - [ ] Humanize timedeltas.
- [ ] Reset stats
- [x] Implement GitHub actions.
  - [ ] Use code quality/anlaysis services (codacy, codeclimate, coverity, coveralls, sonarqube).
  - [ ] Upload coverage in CI.
- [ ] Add "button" images to README.
  - [ ] GitHub Actions checks
  - [ ] External code quality/analysis
- [ ] Make working example of caching in S3.
- [ ] Set up git-changelog.
- [ ] Make it work for instance methods.
- [x] Make `charmonium._time_block` serializable
- [ ] Write about replacing notebooks.
- [ ] Add helper for matplotlib.
