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
- [x] Test that Memoized functions compose
  - Write __determ_hash__ for memoized

# Bug fix release

- [x] Test for repeated use of multiprocessing
  - setstate clears version and reads cache
- [x] Test for f(x), write, read, f.would_hit(x)
  - Index.__setitem__ doesn't delete if last_level[last_key] = val
- [x] Content address object store or use hash(index keys)
  - This makes the object-key deterministic, so if two parallel workers compute the same object, only one gets stored.
  - Requires writes to be atomic
- [x] Make remove orphans optional.
- [x] Found in index but not in obj_store
- [ ] Print log on {invalidation, eviction, orphan, miss, hit}
  - Handle long arg message
  - Humanize timedeltas
  - Print what part of key is invalidated
- [ ] determ_hash Use xxHash
- [ ] Improve determ_hash
  - Catch Pickle TypeError
  - Support out-of-band (zero-copy) pickle-hashing
- [ ] Make determ_hash work for more things
  - Module: hash by contents (like an object). Do I even need a special case here?
  - Objects: include the source-code of methods.
  - C extensions. hashed by the contents of the dynamic library.
  - methods
  - classes
  - fastpath for numpy arrays

# Minor release
- [ ] Read-only memoization
- [ ] file-IO based pickle
- [ ] Make fine_grain* apply to a Memoized level. All benefit from positive externalities.
- [ ] Make resistant to errors
  - Add commit()
  - sys.excepthook
- [ ] Optionally repay stdout on cache hit

# Low priorities
- [ ] Reset stats
- [ ] Implement GitHub actions
  - Use code quality/anlaysis services (codacy, codeclimate, coverity, coveralls, sonarqube)
- [ ] Add "button" images to README.
  - GitHub Actions checks
  - External code quality/analysis
- [ ] Hashable prints log on error
- [ ] Make optional per-call performance logging like ch_time_block.
- [ ] Line-profile big program.
  - It's probably the de/serialization that hurts performance, but I'd like to check.
- [ ] Make working example of caching in S3.
- [ ] Set up git-changelog.
- [ ] Fix frozendict
