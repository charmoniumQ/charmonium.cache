#!/bin/bash

cd "$(dirname "${0}")/.."

check=${check:-}
verbose=${verbose:-}
skip_lint=${skip_lint:-}
htmlcov=${htmlcov:-}
codecov=${codecov:-}

package_name="charmonium.cache"
package_path="./$(echo ${package_name} | sed 's/\./\//g')"
srcs="${package_path} tests/ stubs/ $(find scripts/ -name '*.py')"

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
		poetry run \
			autoflake --recursive ${flag_check_or_in_place} ${srcs}

[[ -n "${skip_lint}" ]] || \
	capture \
		poetry run \
			isort --recursive ${flag_check_only} ${srcs}

[[ -n "${skip_lint}" ]] || \
	capture \
		poetry run \
			black --quiet --target-version py38 ${flag_check} ${flag_verbose_or_quiet} ${srcs}

[[ -n "${skip_lint}" ]] || \
	capture \
		poetry run \
			sh -c "pylint ${flag_verbose} ${package_path} ${other_srcs} || poetry run pylint-exit -efail \${?} > /dev/null"

capture \
	poetry run \
		env PYTHONPATH=".:${PYTHONPATH}" MYPYPATH="./stubs:${MYPYPATH}" \
			mypy --namespace-packages -p ${package_name}
capture \
	poetry run \
		env PYTHONPATH=".:${PYTHONPATH}" MYPYPATH="./stubs:${MYPYPATH}" \
			mypy --namespace-packages $(excluding "stubs" $(excluding "${package_path}" ${srcs}))
# ${flag_verbose} is too verbose here

# Note that I can't use dmypy because I have a package (-p) and files
# to check, which are (unfortunately) mutually exclusive arguments.

capture \
	poetry run \
		pytest --quiet --exitfirst  --cov="${package_path}" --cov-report=term-missing  tests
# I only care about --cov= in the exported package

[[ -z "${htmlcov}" ]] || \
	xdg-open htmlcov/index.html

poetry run \
	coverage html -d htmlcov

[[ -z "${CODECOV_TOKEN}" ]] || \
	capture \
		poetry run \
			codecov

