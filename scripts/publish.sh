#!/usr/bin/env sh

set -e -x
cd "$(dirname "${0}")/.."


if [ "${1}" != "major" -a "${1}" != "minor" -a "${1}" != "patch" ]; then
	echo "Usage: ${0} (major|minor|patch)"
	exit 1
fi

part="${1}"

./scripts/test.sh
./scripts/docs.sh

if [ -n "$(git status --porcelain)" ]; then
	echo "Should be clean commit"
	exit 1
fi

poetry run bump2version "${part}"
poetry build
poetry run twine check dist/*

if [ -z "${dry_run}" ]; then
    read -p "Last chance to abort. Continue?" yn
	if [ "${yn}" = y ]; then
		poetry publish
	fi
fi
