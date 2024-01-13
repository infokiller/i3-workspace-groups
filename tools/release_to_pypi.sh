#!/usr/bin/env bash

# See https://vaneyckt.io/posts/safer_bash_scripts_with_set_euxo_pipefail/
set -o errexit -o errtrace -o nounset -o pipefail

DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "${DIR}/.."
[[ -d dist ]] && rm -rf dist
python -m build
twine upload --verbose dist/*
