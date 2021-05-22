#!/usr/bin/env sh

set -e -x

cd "$(dirname "${0}")/.."

if [ -z "${POETRY_ACTIVE}" ]; then
	nix-shell --run "${0}"
fi

flag_quiet=$([ -n "${verbose}" ] && echo "-v" || echo "-q")

sphinx-build ${flag_quiet} -W -b html docsrc docs
touch docs/.nojekyll
# poetry run gitchangelog
