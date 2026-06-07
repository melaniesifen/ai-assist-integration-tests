#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

python3 -m unittest discover -s tests
python3 -m compileall assistant_stream_harness tests
