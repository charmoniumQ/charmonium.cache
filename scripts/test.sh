#!/bin/bash

cd "$(dirname "${0}")/.."

if [ -z "${POETRY_ACTIVE}" ]; then
	exec nix-shell --run "${0}"
fi

check=${check:-}
verbose=${verbose:-}
skip_lint=${skip_lint:-}
htmlcov=${htmlcov:-}
codecov=${codecov:-}

package_name="charmonium.cache"
package_path="./$(echo ${package_name} | sed 's/\./\//g')"
srcs="${package_path} tests/ typings/ $(find scripts/ -name '*.py')"

# TODO: Rewrite in Python
# TODO: Start from last failure
# TODO: Make colors work
# TODO: Dispatch testing, docs, and publish from the same script

function excluding() {
	# Usage: excluding needle haystack...
	for var in "$@"; do
		if [[ ! "${var}" =~ "${1}" ]]; then
			echo -e "$var "
		fi
	done
}

function now() {
	python -c 'import datetime; print((datetime.datetime.now() - datetime.datetime(1970, 1, 1)).total_seconds())'
}

function capture() {
	local log=$(mktemp)
	local command=("${@}")

	local command_start="$(now)"
	"${command[@]}" &> "${log}"
	local command_exit="${?}"
	local command_end="$(now)"
	local command_duration=$(python3 -c "print('{:.2f}'.format(${command_end} - ${command_start}))")

	if [ -s "${log}" -o "${command_exit}" -ne 0 -o -n "${verbose}" ]; then
		if [ "${command_exit}" -eq 0 ]; then
			echo -e "\033[32;1m\$ ${command[@]} \033[0m"
			cat "${log}"
			echo -e "\033[32;1mexitted ${command_exit} in ${command_duration}s\033[0m"
		else
			echo -e "\033[31;1m\$ ${command[@]} \033[0m"
			cat "${log}"
			echo -e "\033[31;1mexitted ${command_exit} in ${command_duration}s\033[0m"
			exit "${command_exit}"
		fi
	fi
}

flag_verbose_or_quiet=$([ -n "${verbose}" ] && echo "--verbose" || echo "--quiet")
flag_verbose=$([ -n "${verbose}" ] && echo "--verbose")
flag_check_or_in_place=$([ -n "${check}" ] && echo "--check" || echo "--in-place")
flag_check_only=$([ -n "${check}" ] && echo "--check-only")
flag_check=$([ -n "${check}" ] && echo "--check")

[[ -n "${skip_lint}" ]] || \
	capture \
		autoimport $(find ${package_path} -name '*.py' | grep -v "__init__.py") $(find tests -name '*.py') $(find typings -name '*.pyi')

[[ -n "${skip_lint}" ]] || \
	capture \
		isort --recursive ${flag_check_only} ${srcs}

[[ -n "${skip_lint}" ]] || \
	capture \
		black --quiet ${flag_check} ${flag_verbose_or_quiet} ${srcs}

[[ -n "${skip_lint}" ]] || \
	capture \
		sh -c "pylint ${flag_verbose} ${package_path} ${other_srcs} || poetry run pylint-exit -efail \${?} > /dev/null"

#capture poetry run pyright

rm -rf .cache

capture \
	pytest --cov=charmonium/cache --cov-report=term-missing --quiet

rm -rf .cache

capture \
	tox

rm -rf .cache

capture \
	radon cc --min b --show-complexity --no-assert "${package_path}" tests

capture \
	radon mi --min b --show --sort "${package_path}" tests

poetry run \
	coverage html -d htmlcov

[[ -z "${CODECOV_TOKEN}" ]] || \
	capture \
		codecov

[[ -z "${htmlcov}" ]] || \
	xdg-open htmlcov/index.html


if which scc; then
   scc --no-complexity --by-file "${package_path}"
   scc --no-complexity --by-file "tests"
fi
