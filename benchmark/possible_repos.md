https://github.com/abisee/pointer-generator
https://github.com/TellinaTool/nl2bash
https://github.com/afshinrahimi/geomdn
https://github.com/magnumresearchgroup/Magnum-NLC2CMD
https://github.com/thunlp/Few-NERD
https://ucinlp.github.io/autoprompt/
https://github.com/raspberryice/gen-arg
https://github.com/aiqm/torchani

These are the repos I am considering as case-studies, ordered from least likely to most likely.

- https://gitlab.ethz.ch/leitner_lab/xquest_xprophet/-/tree/master
  - Uses Perl not Python; Could be interesting future work though.
- https://github.com/Kortemme-Lab/flex_ddG_tutorial
  - Requires external dependency
- https://socialmediamacroscope.org/standalone/github
  - Depends on external services
- https://github.com/nasa/kepler-pipeline/tree/master/source-code/matlab/pdc
  - Uses Matlab not Python.


- https://github.com/jgr1996/MSci-Project
  - Not enough historical variation
- https://github.com/jgr1996/Diamond-Light-Source/
  - Not enough historical variation
- https://github.com/jakevdp/PythonDataScienceHandbook/
  - Not enough historical variation.
  - https://github.com/jakevdp/PythonDataScienceHandbook/blob/master/notebooks/05.13-Kernel-Density-Estimation.ipynb
  - https://github.com/jakevdp/PythonDataScienceHandbook/blob/master/notebooks/05.10-Manifold-Learning.ipynb
- https://github.com/WillKoehrsen/Data-Analysis
  - Not enough historical variation
- https://github.com/donnemartin/data-science-ipython-notebooks
  - Not enough historical variation
  - https://github.com/donnemartin/data-science-ipython-notebooks/blob/master/scikit-learn/scikit-learn-validation.ipynb
  - https://github.com/donnemartin/data-science-ipython-notebooks/blob/master/kaggle/titanic.ipynb
    - Python 2
- https://github.com/Parsl/Parsl-Workflows
  - vasp: I do not believe this example is complete, as it does not contain any computational step.
  - phosim: Currently many steps are mocked.
  - hedm: Many steps are mocked.
  - bio: External dependency.
  - amber: External dependency.
  - aligner: Too simple to benefit from caching.
- https://github.com/Parsl/arctic_dem
  - Depends on external script: /scratch/06187/cporter/results/region_03_conus/jobfiles
- https://nbviewer.org/github/maayanlab/Zika-RNAseq-Pipeline/blob/master/Zika.ipynb
  - Has too many bang commands. A bang command is a shell command embedded in an IPython script. These would not be able to be cached
- https://github.com/christopherburke/tess-point
  - No long-running entrypoint 
- https://showyourwork.readthedocs.io/en/v0.2.2/projects/
  - This is a projec template for projects that generate papers with generated plots.
  - Most of time is spent compiling TeX, not running Python.
  - Authors often don't use functions. My caching takes place at a function-granularity because it has explicit input/outputs; no easy way to change that.
- https://github.com/inducer/loopy/
- https://github.com/inducer/sumpy
- https://ceesd.illinois.edu/directory/
- https://github.com/GijsMulders/epos
  - Could use tutorials
- https://github.com/raymondEhlers/pachyderm/
  - No main command
- https://github.com/macintoshpie/paropt
  - Bayesian optimizer, no tests; probably has low reuse.
- https://pysyd.readthedocs.io/en/latest/
  - Many of the important functions are impure, so it cannot be cached without significant modifications.
- https://github.com/christopherburke/TESS-ExoClass
  - Instructions: https://docs.google.com/document/d/1jk-jGRqsCWDYwPXtzCveJLUM3Q7ytggWAgTVTx3ed0k/edit#
  - Input data: https://archive.stsci.edu/hlsp/tess-spoc
  - Too much manual intervention after each step.
    - Could try just using the first step.
- https://github.com/exoplanet-dev/case-studies
  - Uses PyMC3, which I can't serialize
    - This can be overcome with minor modifications.
- https://github.com/Kortemme-Lab/ddg
  - Depends on Rosetta.
- https://github.com/MNGuenther/allesfitter
  - Not enough specific historical variation
- https://docs.lightkurve.org/
  - Not enough specific historical variation
  - Uses PyMC3, which I can't serialize.
    - This can be overcome with minor modifications.
- https://github.com/andrzejnovak/NanoSkimmer
  - No input data
- https://github.com/raymondEhlers/reactionPlaneFit
  - No input data
- https://github.com/erykoff/redmapper
  - Tests exist, but no input data for standalone run
- https://github.com/dfm/emcee
  - Could use tutorials or tests.
  - Not enough specific historical variation.
- https://sandialabs.github.io/
- https://software.llnl.gov/
- https://github.com/ORNL
- https://github.com/uiuc-iml/TRINA
  - Testing/intelligent_ui/trainer.py
  - Stuck at `ModuleNotFoundError: No module named 'trina.utils.render_robot_mask'`.
    - Response: It normally gets built when you run `trina_setup.sh` in the root directory. Removing the import and the couple instances in `robot_encoder.py` and running with robot encoding `robot_encodings/cholera_2.json` with lines 8 and 9 deleted
  - Don't know where to locate data
- https://github.com/microsoft/torchgeo
  - Could use tutorials or benchmarks.
  - Ton of dependencies
- https://pipelines.lsst.io/
  - Bug: https://github.com/lsst/sconsUtils/issues/100
- https://github.com/LBJ-Wade/coffea
- https://github.com/charmoniumQ/bollywood-data-analysis
  - Attempts caching already.
- https://github.com/ILLIXR/illixr-analysis
- https://github.com/npirzkal/aXe_WFC3_Cookbook
- https://camb.info/emaildownld.php

Ad:
Do you have a slow data processing pipeline in Python? I'm trying to speed up iterative development by caching intermediate functions, and I'd like to analyze your code (and hopefully improve it) as a case study. https://forms.gle/2dhsGvbbBbthRFbi7

Repo mining:
  - GitHub mining
    - https://ghtorrent.org/
    - http://boa.cs.iastate.edu/
    - https://grep.app/search
  - Other repos:
    - https://ascl.net
- Requirements for pipeline:
  - Language is 90% Python
  - >15 commits
  - Is popular, in terms of stars
  - Has `Pipfile`, `pyproject.toml` with `tool.poetry.dependencies`, or `environment.ya?ml`, which works with its respective tool.
  - Has `__name__ == .main.`
  - https://arxiv.org/pdf/2101.09077.pdf
- Requirements for pytest:
  - Language is 90% Python
  - >15 commits
  - Is popular, in terms of stars
  - Has `Pipfile`, `pyproject.toml` with `tool.poetry.dependencies`, or `environment.ya?ml`, which works with its respective tool.
  - Has GitHub CI, `tox.ini`, or `pyproject.toml` which contains pytest command, which works and all tests pass (remove `--cov=` and `--cov-report=`).
  - Run pytest with cProfile and stats.

Regression testing:
- https://docs.pytest.org/en/6.2.x/cache.html

python -m cProfile -m pytest $pytest_args
