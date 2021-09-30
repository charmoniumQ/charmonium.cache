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
  - [ ] Handle long arg message
- [x] `determ_hash`  should use `xxHash`.
- [x] Improve determ_hash
  - [ ] Catch Pickle TypeError
  - [ ] Catch Pickle ImportError
  - [ ] Support out-of-band (zero-copy) pickle-hashing
- [ ] Make determ_hash work for more things
  - Module: hash by contents (like an object). Do I even need a special case here?
  - Objects: include the source-code of methods.
  - C extensions. hashed by the contents of the dynamic library.
  - methods
  - classes
  - [x] fastpath for numpy arrays
- [ ] Last resort, fall back on `__hash__`.
- [ ] Shortcut for caching a decorator

# Minor release

- [ ] Read-only memoization
- [ ] file-IO based pickle
- [ ] Make `fine_grain*` apply to a `Memoized` level. All benefit from positive externalities.
- [ ] Make resistant to errors.
  - Add `commit()`.
  - Use`sys.excepthook`.
- [ ] Optionally repay stdout on cache hit.
- [ ] Print usage report at the end, with human timedeltas.
- [ ] Use `poetry2nix`.
- [ ] Replace `shell.nix` with `flake.nix`.

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
