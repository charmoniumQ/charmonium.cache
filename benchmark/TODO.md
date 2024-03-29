- [x] Show which part of the key is invalidated
- Performance evaluation
  - [x] Macrobenchmark on commit history of real repositories.
  - [x] Microbenchmark
    - per Memoized: n misses, n hits, size of objects, hashing, deserialization, serialization, object load, object store, function, total on hit, total on miss
    - per MemoizedGroup: index load, index store, index size
- [x] Scrape ASCL.
- [x] Convert Jupyter Notebooks into scripts.
- [x] Query GitHub url to get stars.
  - Hit by ratelimiting.
  - [x] Authenticate to GitHub to raise ratelimit.
  - [x] Implement backoff when hitting ratelimit.
  - [x] Cache results in a global location to avoid ratelimiting.
- [x] Connect ASCL to GitHub in a reliable way.
  - Current strategy: If `code site` is a GitHub repository, we are done. Otherwise, load it (with a timeout), and search through every link in the page, stop when one looks like a `github.com/user/repo` link.
  - [ ] Could improve this by turning `user.github.io` links into a GitHub repository.
  - [ ] Could improve this by turning `github.com/user` links into a GitHub repository.
- [x] Fix charmonium.freeze tests.
- [x] Debug why astronomy pipeline is recomputing when no source code changes.
  - This was due to a variable in matplotlib called `_cache` which is an in-memory cache. `charmonium.freeze` should ignore this variable, because it doesn't change the result of any computation (just speeds it up).
- [x] Document `charmonium.freeze` and `charmonium.cache` debugging process.
- [x] Fix charmonium.freeze for Pandas dataframes.
- [x] Run [eht-imaging] in the experiment
  - Results are promising, 90% time saved on trivial commits.
    - But these commits are too trivial. They are documentation changes could be easily ignored by other strategies.
- [x] Run [astropy] in the experiment.
  - Currently astropy includes a `threading.Lock` object which `charmonium.freeze` can't handle.
    - [x] Avoid hashing the object that contains the lock (preferable, if there is a systematic way of doing so) or make an exception for locks.
  - [x] Find a better example for astropy
- [x] Run testmon on commits. Indicate the testmon overhead and indicate if testmon thinks the script needs to be rerun. Ideally, I would be able to get partial reuse on intermediate values when testmon thinks the script needs to be rerun.
  - However, many of the scripts have a ton of execution time in one critical function. If that function has to be recomputed (it changed syntactically or its predecessor changed semantically), most of the runtime will have to be reexecuted anyway.
  - [x] Run the commits with testmon.
  - [x] Update the output summary.
- [x] Investigate testmon: how does it compare the new source code to the old trace? E.g., does inserting a comment along a taken branch cause an invalidation?
  - Testmon uses the dynamic trace from Coverage.py, but it throws away everything except for the "blocks" graularity. A testmon block is a function or a module. Thus, Testmon uses the dynamic callgraph.
- [x] Find which files get covered by execution trace. Filter to commits which change one of those files. I would want to test fewer or no commits that testmon thinks _don't_ change.
- [ ] Increase automation for scripts.
  - [ ] Add a disable env var, disable group flag, and disable local flag.
  - [ ] If the function is too quick or too quick compared to overhead and auto disable is set, set local disable.
  - [ ] Capture and replay IO. Should go into state vars. Add tests for that.
  - [ ] Add decorator for plots.
  - [ ] Listen for [audit events]; trigger warning and locally disable cache. Add a `assume_pure` flag.
- [ ] Run commits with Joblib. Joblib is a persistent caching decorator which is unsafe. Ideally, `charmonium.cache` should be as fast as Joblib but be correct (match the unmemoized version) in cases where joblib does not.
  - [ ] First, run the commits with Joblib.
  - [ ] Then, update the output summary.
- [ ] Examine how often existing caching decorators are used in GitHub projects. https://grep.app/search?q=joblib.%2Amemory&regexp=true
- [ ] Examine how often existing manuual caching mechanisms (search for kewyord `cache` as a variable name or argument name). Decide accuracy by hand.
- [ ] Increase automation for environments. The experiment runner should install "editable" version the current project with "[dev]" extra if exists and `charmonium.cache` with Conda. The experiment runner should cache this environment. This should be backwards compatible with a manual conda `environment.yml` when the automation fails. Currently, everything uses a manually-written per-project `environment.yml`.
- [ ] Add function for enabling logs? Add timestamp to freeze and cache ops logs.
- [ ] Develop custom audit system. `FileContents` emits custom audit events that cancel our the default ones.
- [ ] Break callgraph into submodule.
  - [ ] Compare keys before and after function execution. If it changes, function is impure.
  - [ ] Scan for references to non-deterministic functions (time, random, sys, os, path), emit audit event.
  - [ ] Cache callgraph and global var names.
- [ ] Write hook on [`sys.meta_path`][sys.meta_path]. You should be able to cache every function in the module by `import charmonium.cache.auto`.
- [ ] Make a dataset consisting of repository, environment specification, command, and estimated time taken. Other researchers can use this to study the evolution of scientific code.
- [x] Improve experiment feedback loop.
  - [x] The results should be cached at a commit-level. They are currently cached at a repo-level.
  - [x] Generate the report after every run (in situ), not just at the end.
  - [x] Make the original executions optional.
- [ ] Integrate with Parsl.
  - [ ] Resp to comment [parsl comment]
- [ ] The outputs of a cached function can be hashed by their progenesis.
  - `result.__getfrozenstate__ = lambda: obj_key`
  - [ ] Look into [lazy_python].

[sys.meta_path]: https://github.com/lihaoyi/macropy/blob/a815f5a58231d8fa65386cd71ff0d15d09fe9fa3/macropy/__init__.py#L16
[lazy_python]: https://pypi.org/project/lazy_python/
[audit events]: https://docs.python.org/3/library/audit_events.html#audit-events
[parsl comment]: https://github.com/Parsl/parsl/issues/1591#issuecomment-954863242
[eht-imaging]: https://github.com/achael/eht-imaging
[astropy]: https://github.com/astropy/astropy

# Conclusion

- Useful to people, but not novel to SEng.
- Write on JOSS.
  - Summarize semester of benchmarks.
  - Use Astropy Jupyter Notebooks.
  - Does this preclude publishing in the future?
- Try to get users.
  - Put into yt, astropy, parsl, Dask.
- Consider user study.
- Ultimately shift to a new project.
  - Possibly GPU acceleration.
  - Summer
