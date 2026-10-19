#!/bin/sh
# UNTESTED: written without access to Docker.
set -eu

alembic upgrade head
# The seed script is a no-op when employees already exist, so restarts keep data.
python -m scripts.seed

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
