#!/usr/bin/env sh
set -e
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run python tools/check_style.py
uv run python tools/write_queries_doc.py --check
uv run pytest -q
