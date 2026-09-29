#!/usr/bin/env zsh
# Evaluation runs need a stable API process; do not watch .venv or reload.
exec .venv/bin/uvicorn api:app
