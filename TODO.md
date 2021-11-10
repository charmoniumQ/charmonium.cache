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
- [ ] Support closures which include `import x` and `from x import y`

# Minor release

- [ ] Do `fsync` before/after load?
- [ ] Do I really need `memoize(..., temporary: bool = False)`?
- [ ] Simplify `tests/test_memoize_parallel.py`.
- [ ] Make `hashable` handle more types:
  - [ ] Classes
- [ ] Shortcut for caching a decorator
- [ ] Support out-of-band (zero-copy) pickle-hashing in `determ_hash`.
- [ ] Read-only memoization
- [ ] file-IO based pickle
- [ ] Make `fine_grain*` apply to a `Memoized` level. All benefit from positive externalities.
- [ ] Make resistant to errors.
  - Add `commit()`.
  - Use`sys.excepthook`.
- [ ] Optionally repay stdout on cache hit.
- [ ] Print usage report at the end, with human timedeltas.
- [ ] Use `poetry2nix`.
- [x] Replace `shell.nix` with `flake.nix`.
- [ ] Write about how memoization interacts with OOP.
- [ ] Write about when memoization is unsound.
- [ ] Record demo, update presentation, link presentation.

# Low priorities

- Regarding logs,
  - [ ] Humanize timedeltas.
  - [ ] Show which part of the key is invalidated
- [ ] Reset stats
- [x] Implement GitHub actions.
  - [ ] Use code quality/anlaysis services (codacy, codeclimate, coverity, coveralls, sonarqube).
  - [ ] Upload coverage in CI.
- [ ] Add "button" images to README.
  - [ ] GitHub Actions checks
  - [ ] External code quality/analysis
- [ ] `hashable` prints log on error
- [ ] Make optional per-call performance logging like `charmonium.time_block`.
- [ ] Line-profile big program.
  - It's probably the de/serialization that hurts performance, but I'd like to check.
- [ ] Make working example of caching in S3.
- [ ] Set up git-changelog.
- [ ] Fix frozendict
- [ ] Make it work for instance methods.
- [ ] Make `charmonium._time_block` serializable
- [ ] Detect impurities, by testing closure vars for modification after running (like IncPy)
- [ ] Detect impurities, by audithooks https://docs.python.org/3/library/audit_events.html
- [ ] Detect impurities, by scanning for references to non-deterministic functions (time, random, sys)
- [ ] Write about replacing notebooks.
