#!/usr/bin/env sh

set -e -x

if [ "${1}" != "major" -a "${1}" != "minor" -a "${1}" != "patch" ]; then
	echo "Usage: ${0} (major|minor|patch)"
	exit 1
fi

part="${1}"

poetry run tox -p
poetry run bump2version "${part}"
poetry build
poetry run twine check dist/*

if [ -z "${dry_run}" ]; then
    read -p "Last chance to abort. Continue?" yn
	if [ "${yn}" = y ]; then
		poetry publish
	fi
fi
