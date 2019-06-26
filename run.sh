#!/bin/sh

source_dir=charmonium
namespace=charmonium
package=charmonium.cache

if [ ! -d env/ ]
then
    python3 -m virtualenv env/
    . ./env/bin/activate
    pip3 install -r requirements.txt -r dev-requirements.txt
fi

. ./env/bin/activate

set -e -x

# I have chosen to make tests a subdirectory of code so that the next
# four commands are simpler

# While [--namespace-discovery][1] has been added, "Note that this
# only affects import discovery – for modules and packages explicitly
# passed on the command line, mypy still searches for __init__.py[i]
# files in order to determine the fully-qualified module/package
# name."
# [1]: https://mypy.readthedocs.io/en/latest/command_line.html#import-discovery
[ -n "${namespace}" ] && touch ${namespace}/__init__.py
mypy -p ${package} --strict
[ -n "${namespace}" ] && rm ${namespace}/__init__.py

python -m pytest --pyargs ${package}.tests

[ -n "${namespace}" ] && touch ${namespace}/__init__.py
pylint ${package} --exit-zero
[ -n "${namespace}" ] && rm ${namespace}/__init__.py

scc ${source_dir}

python3 -c "import setup; print(setup.description)" > ./README.md
