#!/bin/sh
set -eu
python3 -m venv .venv
env -u PYTHONPATH -u PIP_TARGET -u PIP_PREFIX PIP_CONFIG_FILE=/dev/null PIP_USER=false .venv/bin/python -m pip install -r requirements.lock.txt
