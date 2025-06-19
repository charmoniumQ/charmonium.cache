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

# Requested changes to Charmonium.freeze
- [x] Make it work for instance methods.
- [x] Make `charmonium._time_block` serializable
- [ ] Add API for ignoring modules that come from a requirements file or pyproject.toml (based on version instead of contents of module)
  - This is quite difficult because there is no differences between checking the call graph and checking the closed-over variables.
  - Could also just assume they are pure.
  - ```
import wrapt
class ignore_arg(wrapt.ObjectProxy):
    def __getfrozenstate__(self):
        return None
```
- [ ] Make sure adding a loghandler doesn't invalidate cache.
- [ ] Make an API like `@code_version("1.0")` in `charmonium.freeze`. This prevents freeze from recursing into the function.
- [ ] Make a CLI to query the current freeze value of the code. This should be able to be passed as an arg to `@code_version` as above.
- [ ] Make all packages in stdlib be assumed constant.
  - This may not be valid if stdlib has state, e.g. `random`.
- [ ] Break callgraph into submodule.
  - [ ] Scan for references to non-deterministic functions (time, random, sys, os, path), emit audit event.
  - [ ] Cache callgraph and global var names.

# Minor release
- [x] Replace `shell.nix` with `flake.nix`.
- [x] Freeze config should be group-wide or fn-specific instead of global.
- [ ] Add extension API
  - Add API for deleting one entry from cache
  - Call if would be cache hit, else return None
  - Tests!
- [ ] Add helper for caching a stream. When the function recomputes, it should stream values out, while also storing them in a list, and once the stream is finished, store the list.
- [ ] Cache should hit if entry is absent in index but present in obj store ("recover" orphans). In this case, we have the result, but not the metadata. Just create the metadata on the spot and use the computed result.
- [ ] Updating the entry atime only needs to be done if fine_grained_evictions. Notably, fine_grain_persistence should not need a write_lock on the index.
- [ ] Make an Azure lock.
- Make resistant to errors.
  - [x] Add `commit()`. Users can call `commit()` to write the cache index before doing a risky operation or an operation that would invite reuse across processes.
  - [ ] Use`sys.excepthook` to write the cache index before crashing.
  - [ ] Add "medium-grain" persistence; save if the last time we saved was more than X seconds ago.
- [ ] Option to not write atimes to the index. Also, avoid writing the index back if nothing has changed (dirty bit). This is necessary for read-only usages of charmonium.cache. Also reduces contention in highly parallel environments.
- Detect impurities
  - [ ] Listen for [audit events]; trigger warning and locally disable cache. Add a `assume_pure` flag.
  - [ ] Compare global vars and fn arguments before and after running function. charmonium.cache should be able to emulate the side-effects of impure functions.
    - [ ] Check that this restores the state of `random`.
- [ ] Update warning to a subclass. Fix tests.
- [ ] Add helper for matplotlib.
- [ ] Create a better API for group configuration.
- [ ] Do writing-to-disk off the critical path, in a thread.
- [ ] Use environment variable to specify cache location.
- [ ] Have an option for `system_wide_cache` that stores the cache directory in a deterministic (not relative to `$PWD`) path.
- [ ] Do `fsync` before/after load?
- [ ] Optionally cache raised errors
- [ ] Optionally replay stdout (and logs?) on cache hit.
  - The argument against this is that `print("hi")` is an easy way to tell if your function is being re-computed.
- [ ] Print usage report at the end, with human timedeltas.
- [ ] https://stackoverflow.com/questions/31255894/how-to-cache-in-ipython-notebook
- [ ] Humanize timedeltas in logs.
- [ ] Reset stats
- [ ] Support async locks.
- [ ] Consider lock-free index datastructures (could be log-structured).

# Documentation
- [x] Explain how to use logging (ops, perf, freeze).
- [x] Add "button" images to README for GitHub Actions checks.
- [ ] Improve REAMDE
  - [ ] Write "what makes a good candidate" in `README.rst`
  - [ ] Write about group-level configuration in `README.rst`
- [ ] Make working example of caching in S3.
- [ ] Write about replacing notebooks.
- [ ] Write about how memoization interacts with OOP.
- [ ] Write about when memoization is unsound.
- [ ] Record demo, update presentation, link presentation.
  - [ ] Spellcheck API docs?
- [ ] Write about ambiguity in variable names. By reading the source code, you can't tell if a reference is local or global; a local reference can shadow a global one.
- [ ] Fabricate.py + Dask?

# Dev infra improvements
- [ ] Set up git-changelog.
- GitHub Actions
  - [x] Implement basic GitHub Actions.
  - [ ] Use code quality/anlaysis services (codacy, codeclimate, coverity, coveralls, sonarqube).
  - [ ] Upload coverage in CI.
  - [ ] External code quality/analysis
- [ ] Test fine-grained persistence more carefully.
- Improve test coverage
  - [x] Improve test coverage in `charmonium.cache`, `charmonium.freeze`. See `TODO.md` in those repos.
  - [ ] Update test for eviction. Use caplog to detect eviction.
  - [ ] Write test for cascading delete. Use caplog.
  - [ ] Add tests for would hit.
- [ ] Simplify `tests/test_memoize_parallel.py`.
- [ ] Fix how we handle temporary directories in tests and doctests
  - [ ] Do I really need `memoize(..., temporary: bool = False)` in tests?
  - [ ] Make the doctests in `README.rst` work without having to `rm -rf .cache` by hand.
