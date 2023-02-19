---
title: Safely memoizing Python functions
author: Samuel Grayson
csl: acm
bibliography: bib.json
citeproc: true
standalone: true
abstract: >
  Developers working on a data analysis pipeline often make small changes and then test the result of that change by rerunning the pipeline.
  These changes usually only affect a small part of the pipeline, so they only need to rerun that part and its downstream parts to see the impact of their changes.
  Current practices require that they break their program into pieces, give each piece a command-line entrypoint, and describe the pieces and dependencies in a workflow manager.
  This is inefficient, since data has to be serialized and deserialized between subsequent stages, and it often involves a significant amount of boilerplate code.


  Instead, the authors developed a library called `charmonium.cache` that automatically memoizes amenable function calls.
  In subsequent executions of the piepline, these function calls do not need to be rerun if their neither function nor their input changed.
  The authors wrote the library in Python, but it is transferrable to any language with certain reflective facilities.
  The authors evaluate the library on real data pipelines.

---

# Introduction

TODO: Discuss prevalence of data science pipelines. Refer to the bibliography in [@{http://zotero.org/users/6920954/items/R5LZSFAP}].

TODO: Discuss the prevalence of incremental changes in development.

**Problem:** Developers would be able to iterate faster by only rerunning the part of their program that changed or are downstream from such changes without changing their code or writing new code to support that form of execution.

Such a system should be as _safe_ and _precise_ as possible. Safety means that the end result is semantically equivalent to rerunning the entire program from scratch. If the system isn't safe, developers will likely not trust it, and just recompute the results every time. Precision means that the system runs as few tasks as required to generate the result. If the system isn't precise, there is little advantage to using it at all.

## Why Not Workflow Managers

Workflow managers such as Make, Snakemake [@{http://zotero.org/users/6920954/items/PU2YPBG2}], and others[^workflows] can ameliorate this problem. However, they have two burdensom requirements:

[^workflows]: See https://workflows.community/

1. They require the developer to maintain more code specifying the tasks and dependencies within their program. Data analysis is often exploratory, so new tasks can be added frequently. As the workflow configuration file becomes more complex, that file itself becomes a liability for producing stale results. Some Makefiles include `Makefile` as an explicit dependency of every target. Without this rule, the system is unsafe, but with this rule, the system is overly conservative: touching the Makefile invalidates all previously cached results.

2. They require different tasks to run in different processes. Workflow managers simply decide which processes don't need to be re-executed. This means that the tasks do not share memory; all communication has to be serialized and deserialized on the filesystem. Each task needs to implement its own argument parsing. Suppose one needs to add a global parameter; it has to be added to each task's argument parser.

A library written in the data-processing language could be better because it can memoize tasks _within_ the process rather than just memoizing the entire process. This finer granularity allows it to reuse more work. This does not conflict with a workflow manager, and perhaps one could use both: A workflow manager decides which scripts to run, and within that, a memoization library decides which functions of the script to run.

TODO: figure of hierarchical memoization

TODO: figure of boilerplate for processes

# Prior Work

Guo and Engler introduce IncPy in [@{http://zotero.org/users/6920954/items/R5LZSFAP}]. The authors modify the CPython interpreter to track object references in order to support automatic memoization. Modifying the language interpreter is a valid strategy, but it makes it harder to use the technique in new languages or new versions of that language. In fact, IncPy only supports Python 2.6, which has been obsolete for almost ten years at the time of this writing. The alternative strategy is to work _within_ the API of the language.

## In Regresion Test Selection

The task of selecting which functions to run given a code change is similar to identifying which regression tests to select given a code change. There are some important differences:

- Regression test selection can tolerate more unsafety. One can do a first pass using regression test selection, and then use a slower, second pass with the comprehensive test suite in an asynchronous, continuous integration job [@{http://zotero.org/users/6920954/items/LCUERC7L}]; this way the developer gets faster feedback on average. However, in script memoization, there is no "second pass." The whole point of memoization is to speed up the iterative development cycle, but if it isn't safe, developers might disable it during debugging sessions.

Kim et al. introduce TAO in [@{http://zotero.org/users/6920954/items/LCUERC7L}]. TAO is deliberately unsafe, so it would be difficult to apply to iterative development where unsafety is less tolerable.

Pytest-testmon

pytest-rts in [@{http://zotero.org/users/6920954/items/N8FFHD35}].

Ekstazi

## In Program Analysis

Chen et al. introduce a Hybrid Information Flow Analysis for Python Bytecode

Beniget

Mypyc

## In Distributed Schedulers

While Parsl [@{http://zotero.org/users/6920954/items/MII9DUFS}] is primarily oriented towards parallel processing, it does have the ability to cache functions across subsequent process invocations. However, it is not _safe_ with respec to a code change; "Parsl does not traverse the call graph of the app function, so changes inside functions called by an app will not invalidate cached values" ([@{http://zotero.org/users/6920954/items/UCM5XYSP}] in User Manual > Memoization and Checkpointing > App Equivalence).

## Other Approaches

Some developers prefer to use Jupyter Notebooks. Jupyter Notebooks, like an interactive console session, keep results in memory. Users manually select which pieces of their code to re-execute after making code changes. This is useful for prototyping and exploration, but inadvisable for data pipelines that need to be repeatable. The user has to decide by hand which cells to rerun. They might make a mistake and not run a cell that needs to be run, making their end result not reproducible.

# Design

# Evaluation

## Research Questions

## Results

## Threats to Validity

## Future Evaluation

# Conclusion
