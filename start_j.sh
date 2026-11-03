#!/bin/sh
set -eu
exec env -u PYTHONPATH .venv/bin/python j_supervisor.py
