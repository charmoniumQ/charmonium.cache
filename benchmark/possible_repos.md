- https://gitlab.ethz.ch/leitner_lab/xquest_xprophet/-/tree/master
  - Perl
- https://github.com/Kortemme-Lab/flex_ddG_tutorial
  - External dependency
- https://github.com/Kortemme-Lab/ddg
  - No entry point
- https://socialmediamacroscope.org/standalone/github
  - External service dependencies

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

- https://nbviewer.org/github/maayanlab/Zika-RNAseq-Pipeline/blob/master/Zika.ipynb
  - Has too many bang commands
- https://github.com/microsoft/torchgeo
  - Use tutorials or benchmarks
  - Ton of dependencies
- https://github.com/dfm/emcee
  - Use tutorials or tests
  - Not enough specific historical variation
- https://github.com/GijsMulders/epos
  - Use tutorials
- https://pysyd.readthedocs.io/en/latest/
  - Use tutorials or tests
- https://github.com/exoplanet-dev/case-studies
  - Uses PyMC3
- https://github.com/MNGuenther/allesfitter
  - Not enough specific historical variation
- https://docs.lightkurve.org/
  - Not enough specific historical variation
- https://github.com/Parsl/arctic_dem
- https://github.com/Parsl/lsst-pipelines
- https://github.com/Parsl/Parsl-Workflows
- https://github.com/uiuc-iml/TRINA
  - Testing/intelligent_ui/trainer.py
  - Stuck at `ModuleNotFoundError: No module named 'trina.utils.render_robot_mask'`.
  - It normally gets built when you run trina_setup.sh in the root directory
  - removing the import and the couple instances in robot_encoder.py and running with robot encoding robot_encodings/cholera_2.json with lines 8 and 9 deleted
- https://github.com/charmoniumQ/bollywood-data-analysis
  - Attempts caching
- https://github.com/ILLIXR/illixr-analysis

- Luke Olsen
- Andreas Kloeckner
- https://github.com/inducer/loopy/
- https://github.com/inducer/sumpy
- https://ceesd.illinois.edu/directory/

- I should be able to run a few setup commands and then run the code ("works out of the box"). Minimal configuration, dependencies pinned.

- There should be multiple Python functions that take a long time (>1s). The repository can be a polyglot as long as multiple time-intensive stages are eventually wrapped by Python functions. Those functions or functions transitively called by those should change frequently during the project's history.

- The code should not attempt to cache intermediate results (that's what I want to do).

- There should be a commit history of iterative development (>20 commits). There should be a stable CLI entrypoint throughout that history.


- Lightcurve problems
- Astopy problems

- How to isolate?
