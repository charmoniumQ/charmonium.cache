- https://github.com/Kortemme-Lab/flex_ddG_tutorial
  - External dependency
- https://github.com/Kortemme-Lab/ddg
  - No entry point
- https://gitlab.ethz.ch/leitner_lab/xquest_xprophet/-/tree/master
  - Perl
- https://docs.exoplanet.codes/en/latest/
- https://github.com/dfm/emcee
  - Use tutorials or tests
- https://docs.lightkurve.org/
  - Use tutorials or tests
- https://pysyd.readthedocs.io/en/latest/
  - Use tutorials or tests
- https://github.com/MNGuenther/allesfitter
  - Use tutorials
- https://socialmediamacroscope.org/standalone/github
  - External service dependencies
- https://github.com/GijsMulders/epos
  - Use tutorials
- https://github.com/jgr1996/Photoevaporation-BHM
  - Possible
- https://github.com/microsoft/torchgeo
  - Use tutorials or benchmarks
  - Ton of dependencies
  - Needs libc
- https://github.com/charmoniumQ/bollywood-data-analysis
  - Attempts caching
- https://github.com/ILLIXR/illixr-analysis
  - Object bug
- Luke Olsen
- Andreas Kloeckner
- https://github.com/inducer/loopy/
- https://github.com/inducer/sumpy
- https://ceesd.illinois.edu/directory/

- https://github.com/uiuc-iml/TRINA
  - Stuck at `ModuleNotFoundError: No module named 'trina.utils.render_robot_mask'`.

https://nbviewer.org/github/maayanlab/Zika-RNAseq-Pipeline/blob/master/Zika.ipynb


- I should be able to run a few setup commands and then run the code ("works out of the box"). Minimal configuration, dependencies pinned.

- There should be multiple Python functions that take a long time (>1s). The repository can be a polyglot as long as multiple time-intensive stages are eventually wrapped by Python functions. Those functions or functions transitively called by those should change frequently during the project's history.

- The code should not attempt to cache intermediate results (that's what I want to do).

- There should be a commit history of iterative development (>20 commits). There should be a stable CLI entrypoint throughout that history.


- Lightcurve problems
- Astopy problems

- How to isolate?
