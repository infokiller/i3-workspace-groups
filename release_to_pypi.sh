#!/usr/bin/env bash

# See https://vaneyckt.io/posts/safer_bash_scripts_with_set_euxo_pipefail/
set -o errexit -o errtrace -o nounset -o pipefail

cd "$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
[[ -d dist ]] && rm -rf dist
python setup.py sdist bdist_wheel
twine upload --verbose dist/*
