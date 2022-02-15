#!/usr/bin/env sh

set -e -x
cd "$(dirname "${0}")/.."

if [ -z "${POETRY_ACTIVE}" ]; then
	echo "Run with Nix"
	exit 1
fi

if [ "${1}" != "major" -a "${1}" != "minor" -a "${1}" != "patch" ]; then
	echo "Usage: ${0} (major|minor|patch)"
	exit 1
fi

part="${1}"

if [ -z "${skip_checks}" ]; then
	./scripts/test.sh
	./scripts/docs.sh
fi

if [ -n "$(git status --porcelain)" ]; then
	echo "Should be clean commit"
	exit 1
fi

poetry run bump2version "${part}"
rm -rf dist
poetry build
twine check dist/*

if [ -z "${dry_run}" ]; then
    read -p "Last chance to abort. Continue?" yn
	if [ "${yn}" = y ]; then
		poetry publish
		git push
	fi
fi
