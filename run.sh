#!/bin/sh

namespace=charmonium
package=${namespace}.$(ls ${namespace} -X | head -n 1)

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
touch ${namespace}/__init__.py ; mypy -p ${package} ; rm ${namespace}/__init__.py

python -m pytest  --pyargs ${package}.tests

touch ${namespace}/__init__.py ; pylint ${package} --exit-zero ; rm ${namespace}/__init__.py

scc ${namespace}

python3 -c "import ${package}; print(${package}.__doc__)" > ./README.md
