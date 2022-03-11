#!/usr/bin/env sh

set -e -x

cd "$(dirname "${0}")/.."

if [ -z "${VIRTUAL_ENV}" ]; then
	echo "Run with Nix or Poetry"
	exit 1
fi

flag_quiet=$([ -n "${verbose}" ] && echo "-v" || echo "-q")

sphinx-build ${flag_quiet} -W -b html docsrc docs
touch docs/.nojekyll
# poetry run gitchangelog
