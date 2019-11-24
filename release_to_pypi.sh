#!/usr/bin/env bash

# See https://vaneyckt.io/posts/safer_bash_scripts_with_set_euxo_pipefail/
set -o errexit -o errtrace -o nounset -o pipefail

cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
[[ -d dist ]] && rm -rf dist
python setup.py sdist bdist_wheel
twine upload --verbose dist/*
