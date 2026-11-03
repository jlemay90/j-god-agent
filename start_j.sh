#!/bin/sh
set -eu
export J_ENV=production
export GEMINI_MODEL="gemini-3.1-flash-lite"
exec env -u PYTHONPATH .venv/bin/python j_supervisor.py
