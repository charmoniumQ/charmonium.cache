#!/bin/sh
package=$(python3 -c 'import setuptools; print(setuptools.find_packages()[0])')
if [ ! -d env/ ]
then
    python3 -m virtualenv env/
    . ./env/bin/activate
    cat `which pip3`
    cat `pip3 --version`
    cat `which python3`
    cat `python3 --version`
    pip3 install -r requirements.txt -r dev-requirements.txt
fi
. ./env/bin/activate
set -e -x
[ ! -d .cache/ ] && mkdir .cache/
modtime=`stat -c '%Y' requirements.txt`-`stat -c '%Y' dev-requirements.txt`
cache_requirements=./cache/requirements
if test ! -f "${cache_requirements}" || test "${modtime}" = "$(cat \"${cache_requirements}\")"
then
    pip3 install -r dev-requirements.txt -r requirements.txt
    echo "${modtime}" > "${cache_requirements}"
fi
python3 -m mypy -p ${package}
python3 -m pytest tests
python3 -m pylint ${package} tests
scc ${package} tests
