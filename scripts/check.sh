#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> uv sync --extra dev"
uv sync --extra dev

echo "==> pytest"
uv run pytest

echo "==> openspec validate --changes --strict"
npx @fission-ai/openspec@latest validate --changes --strict

echo "==> openspec validate --specs --strict"
npx @fission-ai/openspec@latest validate --specs --strict

echo "All checks passed."
