#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
# No ambient Replit target/site path and no unpinned resolver-selected dependencies.
env -u PYTHONPATH -u PIP_TARGET -u PIP_PREFIX -u PIP_CONSTRAINT -u PIP_REQUIREMENT \
    PIP_CONFIG_FILE=/dev/null PIP_USER=false PYTHONNOUSERSITE=1 \
    .venv/bin/python -m pip install --no-deps -r requirements.lock.txt
env -u PYTHONPATH PYTHONNOUSERSITE=1 .venv/bin/python -m pip check
env -u PYTHONPATH PYTHONNOUSERSITE=1 .venv/bin/python -c \
    'import telegram, google.genai, requests, pydantic, psycopg, zep_cloud, replit.object_storage'
