#!/usr/bin/env sh

set -e -x

cd "$(dirname "${0}")/.."

flag_quiet=$([ -n "${verbose}" ] && echo "-v" || echo "-q")

poetry run sphinx-build ${flag_quiet} -W -b html docs docs/_build
