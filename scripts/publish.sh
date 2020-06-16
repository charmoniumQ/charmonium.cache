#!/usr/bin/env sh

set -e -x

if [ "${1}" != "major" -a "${1}" != "minor" -a "${1}" != "patch" ]; then
	echo "Usage: ${0} (major|minor|patch)"
	exit 1
fi

part="${1}"

if [ -z "${skip_test}" ]; then
	./scripts/test.sh
fi
if [ -z "${skip_docs}" ]; then
	./scripts/docs.sh
fi
poetry run bump2version "${part}"
if [ -z "${dry_run}" ]; then
	poetry publish --build
fi
