#!/bin/sh
set -eu
export J_ENV=production
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.1-flash-lite}"
# Local guardrail; not a Google quota guarantee.
export J_DAILY_TOKEN_LIMIT="${J_DAILY_TOKEN_LIMIT:-2000000}"
exec env -u PYTHONPATH .venv/bin/python j_supervisor.py
