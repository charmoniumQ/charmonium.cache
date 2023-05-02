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
- See `benchmark/TODO.md`.

# Minor release
- [x] Add "button" images to README for GitHub Actions checks.
- [ ] Documentation
  - [x] Explain how to use logging (ops, perf, freeze).
  - [ ] Write about how memoization interacts with OOP.
  - [ ] Write about when memoization is unsound.
  - [ ] Record demo, update presentation, link presentation.
- Detect impurities
  - [ ] Listen for [audit events]; trigger warning and locally disable cache. Add a `assume_pure` flag.
- [ ] Fix how we handle temporary directories in tests and doctests
  - [ ] Do I really need `memoize(..., temporary: bool = False)` in tests?
  - [ ] Make the doctests in `README.rst` work without having to `rm -rf .cache` by hand.
- [ ] Make it work for instance methods.
- [ ] Update API doc system.
  - [ ] Spellcheck API docs?
- [ ] Update warning to a subclass. Fix tests.
- [ ] Make resistant to errors.
  - Add `commit()`. Users can call `commit()` to write the cache index before doing a risky operation or an operation that would invite reuse across processes.
  - Use`sys.excepthook` to write the cache index before crashing.
- [ ] Add helper for matplotlib.
- [ ] Write about replacing notebooks.
- [ ] Create a better API for group configuration.
- [ ] Break callgraph into submodule.
  - [ ] Scan for references to non-deterministic functions (time, random, sys, os, path), emit audit event.
  - [ ] Cache callgraph and global var names.
- [ ] Add API for ignoring modules that come from a requirements file or pyproject.toml (based on version instead of contents of module)
- ```
import wrapt
class ignore_arg(wrapt.ObjectProxy):
    def __getfrozenstate__(self):
        return None
```
- [ ] Write about ambiguity in variable names. By reading the source code, you can't tell if a reference is local or global; a local reference can shadow a global one.
- [ ] Do writing-to-disk off the critical path, in a thread.
- [ ] Cache should hit if entry is absent in index but present in obj store ("recover" orphans). In this case, we have the result, but not the metadata. Just create the metadata on the spot and use the computed result.
- [ ] Test fine-grained persistence more carefully.
- [ ] Make all packages in stdlib be assumed constant.
  - This may not be valid if stdlib has state, e.g. `random`.
- Improve test coverage
  - [ ] Update test for eviction. Use caplog to detect eviction.
  - [ ] Write test for cascading delete. Use caplog.
  - [ ] Add tests for would hit.
  - [x] Improve test coverage in charmonium.cache, charmonium.determ_hash. See `TODO.md` in those repos.
- [ ] Compare global vars and fn arguments before and after running function. charmonium.cache should be able to emulate the side-effects of impure functions.
  - [ ] Check that this restores the state of `random`.
- [ ] Use environment variable to specify cache location.
- [ ] Have an option for `system_wide_cache` that stores the cache directory in a deterministic (not relative to `$PWD`) path.
- [ ] Do `fsync` before/after load?
- [ ] Simplify `tests/test_memoize_parallel.py`.
- [ ] Make `fine_grain*` apply to a `Memoized` level. All benefit from positive externalities.
  - There is an argument against this. A user could puprosefully make a low-frequency call fine-grained but not a high-frequency call. This would reduce contention while still providing a checkpoint wihtin the program.
- [ ] Optionally repay stdout (and logs?) on cache hit.
- [ ] Make sure adding a loghandler doesn't invalidate cache.
- [ ] Print usage report at the end, with human timedeltas.
- [x] Replace `shell.nix` with `flake.nix`.
- [ ] https://stackoverflow.com/questions/31255894/how-to-cache-in-ipython-notebook
- Regarding logs,
  - [ ] Humanize timedeltas.
- [ ] Reset stats
- [x] Implement GitHub actions.
  - [ ] Use code quality/anlaysis services (codacy, codeclimate, coverity, coveralls, sonarqube).
  - [ ] Upload coverage in CI.
  - [ ] External code quality/analysis
- [ ] Make working example of caching in S3.
- [ ] Set up git-changelog.
- [x] Make `charmonium._time_block` serializable
- [ ] Make an API like `@code_version("1.0")` in `charmonium.freeze`. This prevents freeze from recursing into the function.
- [x] Freeze config should be group-wide or fn-specific instead of global.
- [ ] Improve REAMDE
  - [ ] Write "what makes a good candidate" in `README.rst`
  - [ ] Write about group-level configuration in `README.rst`
- [ ] Have option for semi-fine grain persistence: Every N seconds, persist.
