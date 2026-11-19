#!/bin/sh
set -eu
dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "${FN_CONTROL_PYTHON:-python3}" "$dir/forward.py" "$@"
